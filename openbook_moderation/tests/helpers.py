from openbook_moderation.models import ModeratedObject


def approve_verify_moderated_object(object_id, user):
    moderated_object = ModeratedObject.objects.filter(object_id=object_id).first()
    user.approve_moderated_object(moderated_object)
    user.verify_moderated_object(moderated_object)
