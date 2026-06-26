import uuid
from logging import Logger

from slack_bolt import Ack
from slack_bolt.context.async_context import AsyncBoltContext
from slack_sdk.web.async_client import AsyncWebClient

async def handle_patchnote_approve(
    ack: Ack,
    body: dict,
    client: AsyncWebClient,
    context: AsyncBoltContext,
    logger: Logger,
):
    """Mark a PatchNote release note as approved and update the database."""
    await ack()
    await _update_note_status(body, client, context, logger, approved=True)

async def handle_patchnote_reject(
    ack: Ack,
    body: dict,
    client: AsyncWebClient,
    context: AsyncBoltContext,
    logger: Logger,
):
    """Mark a PatchNote release note as rejected and update the database."""
    await ack()
    await _update_note_status(body, client, context, logger, approved=False)

async def _update_note_status(
    body: dict,
    client: AsyncWebClient,
    context: AsyncBoltContext,
    logger: Logger,
    approved: bool,
):
    from db.database import AsyncSessionLocal
    from db.crud import update_note_status
    from db.models import ApprovalStatus

    try:
        note_id_str = body["actions"][0]["value"]
        note_id = uuid.UUID(note_id_str)
        channel_id = context.channel_id
        message_ts = body["message"]["ts"]
        user_id = context.user_id

        status = ApprovalStatus.approved if approved else ApprovalStatus.rejected

        async with AsyncSessionLocal() as session:
            note = await update_note_status(
                session=session,
                note_id=note_id,
                status=status
            )
        
        if note is None:
            logger.warning(f"Note {note_id} not found when updating status")
            return
        
        label = "✅ Approved" if approved else "❌ Rejected"
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            thread_ts=message_ts,
            text=f"{label} this PatchNote.",
        )

        logger.info(f"Note {note_id} marked as {status.value} by {user_id}")
    
    except Exception as e:
        logger.exception(f"Failed to update PatchNote status: {e}")



    