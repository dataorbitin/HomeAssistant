import logging

from sqlalchemy import func, select

from app.db.models import (
    DeliveryStatus,
    Direction,
    Message,
    RequestStatus,
    ServiceCategory,
    ServiceRequest,
    ServiceRequestVendor,
    Vendor,
    VendorFeedback,
    utcnow,
)
from app.db.repositories.common import insert_for
from app.schemas.intent import Intent
from app.services.ai_service import AIUnavailable, IntentExtractor
from app.services.conversation_service import ConversationService
from app.services.resident_service import ResidentService
from app.services.vendor_service import VendorService

log = logging.getLogger(__name__)


class MessageService:
    def __init__(self, settings, ai: IntentExtractor):
        self.settings, self.ai = settings, ai

    async def process(self, session, incoming):
        # Everything through creating the outbox row commits as one transaction.
        instance = self.settings.evolution_api_instance
        existing = await session.scalar(
            select(Message.id).where(
                Message.instance == instance,
                Message.direction == Direction.INBOUND,
                Message.external_message_id == incoming.external_message_id,
            )
        )
        if existing:
            return None
        resident = await ResidentService.find_or_create(
            session, incoming.phone_number, self.settings.default_society_name
        )
        if not resident.active:
            return None
        conversation = await ConversationService.find_or_create(session, resident.id)
        history = await ConversationService.recent_context(session, conversation.id, self.settings)
        inbound_id = await session.scalar(
            insert_for(session, Message)
            .values(
                resident_id=resident.id,
                conversation_id=conversation.id,
                instance=instance,
                external_message_id=incoming.external_message_id,
                direction=Direction.INBOUND,
                message_type="text",
                message_text=incoming.text,
                received_at=incoming.timestamp,
                raw_payload=incoming.raw if self.settings.store_raw_payloads else None,
            )
            .on_conflict_do_nothing(index_elements=["instance", "direction", "external_message_id"])
            .returning(Message.id)
        )
        if inbound_id is None:
            return None
        categories = list(
            (
                await session.scalars(
                    select(ServiceCategory).where(ServiceCategory.active.is_(True))
                )
            ).all()
        )
        try:
            intent = await self.ai.extract(incoming.text, history, [c.slug for c in categories])
        except AIUnavailable:
            reply = (
                "Sorry, I couldn't understand your message right now. "
                "Please send your service requirement again in a new message."
            )
        else:
            if intent.intent == Intent.FIND_SERVICE:
                reply = await self.find_service(
                    session, resident, incoming, inbound_id, intent, categories
                )
            elif intent.intent == Intent.GREETING:
                reply = (
                    "Hi! I'm Home Assistant for Megapolis, Hinjewadi Phase 3. "
                    "Tell me what you need help with, such as a plumber or electrician."
                )
            elif intent.intent == Intent.THANK_YOU:
                reply = "You're welcome! Let me know if you need anything else."
            elif intent.intent == Intent.FEEDBACK:
                reply = await self.record_feedback(session, resident, intent)
            else:
                reply = "What service do you need help with? Please describe the problem."
        outbound = Message(
            resident_id=resident.id,
            conversation_id=conversation.id,
            instance=instance,
            in_reply_to_id=inbound_id,
            direction=Direction.OUTBOUND,
            message_type="text",
            message_text=reply,
            delivery_status=DeliveryStatus.PENDING,
        )
        session.add(outbound)
        await session.flush()
        log.info(
            "message_processed intent=%s",
            intent.intent.value if "intent" in locals() else "UNAVAILABLE",
        )
        return outbound.id

    async def find_service(self, session, resident, incoming, inbound_id, intent, categories):
        category = next((c for c in categories if c.slug == intent.service_category), None)
        society = resident.society
        request = ServiceRequest(
            resident_id=resident.id,
            service_category_id=category.id if category else None,
            source_message_id=inbound_id,
            original_message=incoming.text,
            interpreted_requirement=intent.requirement or incoming.text,
            urgency=intent.urgency,
            locality=society.locality if society else None,
            preferred_time=intent.preferred_time,
            status=RequestStatus.MATCHING,
        )
        session.add(request)
        await session.flush()
        ranked = await VendorService().recommend(session, category, society)
        if not ranked:
            request.status = RequestStatus.NEW
            label = category.name.lower() if category else "requested service"
            area = society.name if society else "your area"
            return (
                f"Sorry, I don't have a {label} contact available in {area} yet. "
                "I'm expanding the service network and have recorded your requirement."
            )
        for rank, item in enumerate(ranked, 1):
            session.add(
                ServiceRequestVendor(
                    service_request_id=request.id,
                    vendor_id=item.vendor.id,
                    rank=rank,
                    ranking_score=item.score,
                )
            )
        lines = [
            f"I found {len(ranked)} providers for {category.name.lower()} who may be able to help:",
            "",
        ]
        for rank, item in enumerate(ranked, 1):
            vendor = item.vendor
            lines.extend(
                [
                    f"{rank}. {vendor.business_name or vendor.name}",
                    f"Rating: {vendor.rating if vendor.rating is not None else 'Not yet rated'}",
                    f"Verified: {'Yes' if vendor.verified else 'Not yet'}",
                    f"Contact: {vendor.primary_phone}",
                    "",
                ]
            )
        lines.append(
            "Please tell me which one you contacted (1, 2 or 3). "
            "After the service, send the vendor number and a rating from 1 to 5."
        )
        return "\n".join(lines)

    async def record_feedback(self, session, resident, intent):
        request = await session.scalar(
            select(ServiceRequest)
            .where(ServiceRequest.resident_id == resident.id)
            .order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
            .limit(1)
        )
        if request is None or intent.recommendation_rank is None:
            return "Please tell me the vendor number from my latest recommendation and your rating (1 to 5), or which one you contacted."
        recommendation = next(
            (r for r in request.recommendations if r.rank == intent.recommendation_rank), None
        )
        if recommendation is None:
            return "I couldn't match that number to your latest request. Please clarify which recommended vendor you mean."
        if request.status == RequestStatus.CANCELLED:
            return "That request was cancelled. Please describe the service you need help with."
        if intent.contacted:
            recommendation.contacted = True
            recommendation.selected = True
            if request.status != RequestStatus.COMPLETED:
                request.status = RequestStatus.CONTACTED
        if intent.rating is None:
            return (
                "Thanks, I've recorded which vendor you contacted."
                if intent.contacted
                else "Please send your rating from 1 to 5 along with the vendor number."
            )
        # Serialize aggregate updates when different residents review the same vendor.
        vendor = await session.scalar(
            select(Vendor).where(Vendor.id == recommendation.vendor_id).with_for_update()
        )
        feedback_id = await session.scalar(
            insert_for(session, VendorFeedback)
            .values(
                service_request_id=request.id,
                resident_id=resident.id,
                vendor_id=vendor.id,
                rating=intent.rating,
                feedback=intent.feedback,
            )
            .on_conflict_do_nothing(
                index_elements=["service_request_id", "resident_id", "vendor_id"]
            )
            .returning(VendorFeedback.id)
        )
        if feedback_id is None:
            return "Your feedback for this vendor and request is already recorded. Thank you!"
        vendor.rating = await session.scalar(
            select(func.avg(VendorFeedback.rating)).where(VendorFeedback.vendor_id == vendor.id)
        )
        if request.status != RequestStatus.COMPLETED:
            vendor.total_jobs += 1
            if intent.rating >= 3:
                vendor.successful_jobs += 1
        request.status = RequestStatus.COMPLETED
        request.completed_at = utcnow()
        recommendation.selected = True
        recommendation.contacted = True
        return "Thank you! I've recorded your feedback and marked this request completed."
