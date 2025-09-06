from app.services.services.capsules.base_builder import BaseCapsuleBuilder

class MotherTongueBuilder(BaseCapsuleBuilder):
    def get_details(self, **kwargs):
        print("--> ✅ Entré dans le MotherTongueBuilder pour les langues.")
        return {"message": "Capsule de langue maternelle"}