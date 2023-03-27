class UserPayload:
    def __init__(self, id: str, name: str, email: str):
        self.id = id
        self.name = name
        self.email = email

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}


class SpacePayload:
    def __init__(self, id: str, name: str, slug: str):
        self.id = id
        self.name = name
        self.slug = slug

    def to_dict(self):
        return {"id": self.id, "name": self.name, "slug": self.slug}
