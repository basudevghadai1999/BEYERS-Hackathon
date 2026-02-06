from google.adk import Application, InProcessTransport
from app.agents.metrics_agent import metrics_agent
from app.agents.logs_agent import logs_agent
from app.agents.deploy_agent import deploy_agent
# from app.agents.commander import commander_agent


def bootstrap_app() -> Application:
    """
    Initializes the ADK application and registers agents.
    """
    transport = InProcessTransport()

    app = Application(transport=transport)

    # Registering the agents
    app.register_agent(metrics_agent)
    app.register_agent(logs_agent)
    app.register_agent(deploy_agent)

    return app
