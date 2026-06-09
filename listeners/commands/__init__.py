from slack_bolt.async_app import AsyncApp
from listeners.commands.patchnote_command import handle_patchnote_command

def register(app: AsyncApp):
    app.command("/patchnote")(handle_patchnote_command)

