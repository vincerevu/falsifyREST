from .actor import Actor


class ActorManager:
    def __init__(self, actors: list[Actor] | None = None):
        self._actors = {actor.id: actor for actor in actors or []}

    def add(self, actor: Actor) -> Actor:
        self._actors[actor.id] = actor
        return actor

    def get(self, actor_id: str) -> Actor:
        return self._actors[actor_id]

    def other_than(self, actor_id: str, role: str | None = None) -> Actor:
        return next(actor for actor in self._actors.values() if actor.id != actor_id and (role is None or actor.role == role))

    def all(self) -> list[Actor]:
        return list(self._actors.values())
