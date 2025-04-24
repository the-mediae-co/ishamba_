from django.contrib.auth import get_user_model

User = get_user_model()


def get_action_agent(action):
    """
    The 'agent' is a user who performed an action on behalf of the actor.
    There is no provision to store the agent object in the action so instead,
    the agent id is stored as extra data in the action. Here we get the actual
    object from the database.
    """
    if action.data:
        agent_id = action.data.get('agent_id')
        if agent_id:
            try:
                return User.objects.get(id=agent_id)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                return None
