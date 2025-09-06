from app.services.services.capsules.base_builder import BaseCapsuleBuilder

class PythonBuilder(BaseCapsuleBuilder):
    def get_details(self, **kwargs):
        print("--> ✅ Entré dans le PythonBuilder pour la programmation.")
        return {"message": "Capsule de programmation Python"}