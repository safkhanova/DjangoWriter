"""The «Redaktor» group: everything the site owner edits, nothing technical."""

EDITOR_GROUP = "Redaktor"

# app_label -> model -> allowed actions
EDITOR_PERMISSIONS = {
    "content": {
        "section": ["view", "add", "change"],
        "category": ["view", "add", "change", "delete"],
        "tag": ["view", "add", "change", "delete"],
        "article": ["view", "add", "change", "delete"],
        "articleblock": ["view", "add", "change", "delete"],
        "articleimage": ["view", "add", "change", "delete"],
    },
    "core": {
        "sitesettings": ["view", "change"],
        "hero": ["view", "add", "change", "delete"],
        "herotag": ["view", "add", "change", "delete"],
        "sociallink": ["view", "add", "change", "delete"],
        "contacttopic": ["view", "add", "change", "delete"],
        "contactmessage": ["view", "change", "delete"],
    },
    "newsletter": {
        "subscriber": ["view", "change", "delete"],
        "newsletterissue": ["view", "add"],
    },
}


def sync_editor_group(apps=None):
    """Create/refresh the group. Usable from a data migration (pass `apps`) or a shell."""
    if apps is None:
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
    else:
        Group = apps.get_model("auth", "Group")
        Permission = apps.get_model("auth", "Permission")
        ContentType = apps.get_model("contenttypes", "ContentType")

    group, _ = Group.objects.get_or_create(name=EDITOR_GROUP)
    perms = []
    for app_label, models in EDITOR_PERMISSIONS.items():
        for model, actions in models.items():
            ct, _ = ContentType.objects.get_or_create(app_label=app_label, model=model)
            for act in actions:
                perm, _ = Permission.objects.get_or_create(
                    content_type=ct, codename=f"{act}_{model}", defaults={"name": f"Can {act} {model}"},
                )
                perms.append(perm)
    group.permissions.set(perms)
    return group
