from app.services.services.capsules.base_builder import BaseCapsuleBuilder

class SqlBuilder(BaseCapsuleBuilder):
    def get_details(self, **kwargs):
        print("--> ✅ Entré dans le SqlBuilder pour la programmation.")
        return {"message": "Capsule de programmation SQL"}