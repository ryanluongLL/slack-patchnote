from slack_bolt.async_app import AsyncApp

from .feedback_buttons import handle_feedback_button
from .patchnote_feedback import handle_patchnote_approve, handle_patchnote_reject

def register(app: AsyncApp):
    app.action("feedback")(handle_feedback_button)
    app.action("patchnote_approve")(handle_patchnote_approve)
    app.action("patchnote_reject")(handle_patchnote_reject)