"""
Data structures & functions for the object-based permissions in Lookit.

These must be defined *outside* of the database/guardian tables for two
purposes:
1) serving as a source of truth,
and
2) usage in migrations.

We are using naming conventions that build upon that set by Django itself,
while adding some structural and syntactical elements that help us reason
about permissions in a more queryset-centric way.

As of 2.0, the default per-model permissions added by django.contrib.auth
include:

- ${app_name}.add_${model}
- ${app_name}.change_${model}
- ${app_name}.delete_${model}
- ${app_name}.view_${model}

To enhance this while still leveraging the generated defaults, we have
a few additional field-specific conventions.

- ${app_name}.edit_${model}__${field}
- ${app_name}.read_${model}__${field}

In this context, "Edit" is analogous to "Change", but restricted to a single
field within the specified model. Similarly, "Read" is analogous to "View"
for a single field within a model.

If the specified field is a relationship of some kind (OneToOne, ForeignKey,
etc.) then the model-level variant of the permission (i.e. "Change" or "View")
applies, but only to the *related* model instance(s). The "dunder" syntax should
feel familiar from querysets, and allows for for arbitrary nesting as such:

- ${app_name}.read_${model}__${field}__${subfield}__...

and even filters, using postfixed parenthetical key-value pairs:

read_study__responses(is_preview=True)

The final subfield may have or'd regex-like syntax for multiple fields,
like so:

read_study__[name|public|state|min_age_years|max_age_years|...]

To complete the correspondence between per-model and per-object permissions,
we need two additional field-level permissions to associate and dissociate
existing instances of the relation's specified model.

- ${app_name}.associate_${model}__${field}
- ${app_name}.dissociate_${model}__${field}

This allows us to be MECE with the "Add" and "Delete" permissions of the
related model.

There will be the occasional case where we wish to specify data that is
either a composite of many fields, or some kind of summary data.
Given the 100 char max length of Permission, we can't list too many
fields or a complex queryset serialization, so there's the choice
of arbitrary delimiters in ANGRY_SNAKE_CASE, caret-delimited style:

read_study__<ANALYTICS>
read_study__<DETAILS>

This gives the permission author the flexibility to "kick the can down the
road" in terms of properly segmenting permissions, or represent things
that simply aren't modeled in the database.
"""

from enum import Enum

# Upgrade to python 3.8 for cached_property
# from functools import cached_property
from typing import NamedTuple, Tuple

# from django.contrib.auth.models import Group
# from guardian.shortcuts import assign_perm


class _PermissionName(Enum):
    # Model-level
    ADD = "add"
    CHANGE = "change"
    DELETE = "delete"
    VIEW = "view"
    # Field-level
    EDIT = "edit"
    READ = "read"
    ASSOCIATE = "associate"
    DISSOCIATE = "dissociate"


class _PermissionParts(NamedTuple):
    permission: str
    model_name: str
    relationship_path: Tuple[str, ...]
    target_fields: Tuple[str, ...]


class _PermissionMeta(NamedTuple):
    """Immutable, object-oriented wrapper for Study and Lab permissions.

    We exploit the fact that private fields are not returned when iterating
    over tuples.

    Properties:
        codename: a string codename. See module docstring for conventions.
        description: a string description.
    """

    codename: str
    description: str

    @property
    def parts(self) -> _PermissionParts:
        perm_and_model, *field_vector = self.codename.split("__")
        permission, model_name = perm_and_model.split("_")

        if field_vector:
            final_field_spec = field_vector.pop()
            target_fields = tuple(final_field_spec.strip("[]").split("|"))
        else:
            target_fields = ()

        return _PermissionParts(
            permission=permission,
            model_name=model_name,
            relationship_path=tuple(field_vector),
            target_fields=target_fields,
        )

    @property
    def permission(self) -> str:
        return self.parts.permission

    @property
    def model_name(self) -> str:
        return self.parts.model_name

    @property
    def relationship_path(self) -> Tuple[str, ...]:
        return self.parts.relationship_path

    @property
    def target_fields(self) -> Tuple[str, ...]:
        return self.parts.target_fields

    @classmethod
    def from_parts(
        cls,
        permission: str,
        model_name: str,
        relationship_path: Tuple[str, ...],
        target_fields: Tuple[str, ...],
        description: str,
    ):
        codename = f"{permission}_{model_name}"
        if relationship_path:
            codename += f"__{'__'.join(relationship_path)}"
        if target_fields:
            if len(target_fields) > 1:
                codename += f"__[{'|'.join(target_fields)}]"
            else:
                codename += f"__{target_fields[0]}"

        return cls(codename, description)


def create_groups_for_instance(
    model_instance, group_enum, group_class, perm_class, group_object_permission_model
):
    uuid_segment = str(model_instance.uuid)[:7]
    object_name = model_instance._meta.object_name
    unique_group_tag = (
        f"{object_name} :: {model_instance.name[:7]}... ({uuid_segment}...)"
    )

    for group_spec in group_enum:
        # Group name is going to be something like "READ :: Lab :: MIT (0235dfa...)
        group_name = f"{group_spec.name} :: {unique_group_tag}"
        group = group_class.objects.create(name=group_name)

        for permission_meta in group_spec.value:
            permission = perm_class.objects.get(codename=permission_meta.codename)

            group_object_permission_model.objects.create(
                content_object=model_instance, permission=permission, group=group
            )
            group.save()

        setattr(model_instance, f"{group_spec.name.lower()}_group", group)

    model_instance.save()