"""Conversation list, detail, and deletion endpoints."""

import uuid

from fastapi import APIRouter, Query, Response, status

from chatbot.api.deps import SessionDep
from chatbot.api.errors import ApiError
from chatbot.api.schemas import (
    AttemptSummary,
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    MessageOut,
    UsageOut,
)
from chatbot.application.conversations import (
    ConversationView,
    delete_conversation,
    list_conversations,
    read_conversation,
)
from chatbot.application.cursor import CursorError
from chatbot.domain.enums import AttemptStatus, Role
from chatbot.persistence.tables import GenerationAttempt

router = APIRouter(prefix="/conversations", tags=["conversations"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 20


@router.get("", response_model=ConversationListResponse)
async def list_conversations_endpoint(
    session: SessionDep,
    cursor: str | None = Query(default=None, description="Opaque cursor from a previous page."),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> ConversationListResponse:
    """List conversations, most recently updated first."""
    try:
        page = await list_conversations(session, limit=limit, cursor_token=cursor)
    except CursorError as error:
        raise ApiError(
            "invalid_cursor",
            "The pagination cursor is not valid.",
            status_code=400,
            details={"reason": str(error)},
        ) from error

    return ConversationListResponse(
        items=[
            ConversationSummary(
                id=item.conversation.id,
                title=item.conversation.title,
                created_at=item.conversation.created_at,
                updated_at=item.conversation.updated_at,
                active_attempt_id=item.active_attempt_id,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(
    conversation_id: uuid.UUID,
    session: SessionDep,
) -> ConversationDetail:
    """Return one conversation with its transcript."""
    view = await read_conversation(session, conversation_id)
    if view is None:
        raise ApiError(
            "conversation_not_found",
            "That conversation does not exist.",
            status_code=404,
        )
    return _to_detail(view)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_endpoint(
    conversation_id: uuid.UUID,
    session: SessionDep,
) -> Response:
    """Permanently delete a conversation, its messages, and its attempts."""
    deleted = await delete_conversation(session, conversation_id)
    if not deleted:
        raise ApiError(
            "conversation_not_found",
            "That conversation does not exist.",
            status_code=404,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_detail(view: ConversationView) -> ConversationDetail:
    conversation = view.conversation
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        active_attempt_id=view.active_attempt_id,
        messages=[
            MessageOut(
                id=message_view.message.id,
                role=Role(message_view.message.role),
                seq=message_view.message.seq,
                content=message_view.message.content,
                created_at=message_view.message.created_at,
                attempt=_to_attempt_summary(message_view.attempt, retryable=message_view.retryable),
            )
            for message_view in view.messages
        ],
    )


def _to_attempt_summary(
    attempt: GenerationAttempt | None,
    *,
    retryable: bool,
) -> AttemptSummary | None:
    if attempt is None:
        return None
    usage = None
    if any(
        value is not None
        for value in (
            attempt.input_tokens,
            attempt.output_tokens,
            attempt.thought_tokens,
            attempt.total_tokens,
        )
    ):
        usage = UsageOut(
            input_tokens=attempt.input_tokens,
            output_tokens=attempt.output_tokens,
            thought_tokens=attempt.thought_tokens,
            total_tokens=attempt.total_tokens,
        )
    return AttemptSummary(
        id=attempt.id,
        status=AttemptStatus(attempt.status),
        model=attempt.model,
        attempt_no=attempt.attempt_no,
        retryable=retryable,
        error_code=attempt.error_code,
        usage=usage,
    )
