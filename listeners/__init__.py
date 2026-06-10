from slack_bolt.async_app import AsyncApp

from listeners import actions, commands, events, views


def register_listeners(app: AsyncApp):
    actions.register(app)
    commands.register(app)
    events.register(app)
    views.register(app)
