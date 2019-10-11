# -*- coding: utf-8 -*-
# Generated by Django 1.11.21 on 2019-07-03 16:27
# This migration only exists because you can't reverse the deletion of a non-null field with no specified default.
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("studies", "0047_add_existing_conditions")]

    operations = [
        migrations.RenameField(
            model_name="eligibleparticipantquerymodel",
            old_name="include_conditions",
            new_name="require_conditions",
        ),
        migrations.RenameField(
            model_name="eligibleparticipantquerymodel",
            old_name="include_languages",
            new_name="require_languages",
        ),
    ]