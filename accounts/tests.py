import datetime

from django.test import TestCase
from django_dynamic_fixture import G
from lark.exceptions import UnexpectedCharacters

from accounts.models import Child, User
from accounts.queries import get_child_eligibility
from studies.fields import GESTATIONAL_AGE_CHOICES
from studies.models import Lab, Study, StudyType


class UserModelTestCase(TestCase):
    def setUp(self):
        self.lab_researcher = G(
            User, is_active=True, is_researcher=True, nickname="Lab Researcher"
        )

        self.unaffiliated_researcher = G(
            User, is_active=True, is_researcher=True, nickname="Study Researcher"
        )

        self.unaffiliated_researcher.labs.clear()

        self.participant = G(
            User, is_active=True, is_researcher=False, nickname="Participant"
        )
        self.lab = G(Lab, name="MIT", approved_to_test=True)
        self.study = G(Study, name="Test Study", lab=self.lab, built=True)

        self.study.researcher_group.user_set.add(self.unaffiliated_researcher)

        self.lab.researchers.add(self.lab_researcher)

    def test_lab_researcher_can_create_study(self):
        self.assertTrue(self.lab_researcher.can_create_study())

    def test_unaffiliated_researcher_cannot_create_study(self):
        self.assertFalse(self.unaffiliated_researcher.can_create_study())


class CriteriaExpressionTestCase(TestCase):
    def setUp(self):
        self.study_type = G(StudyType, name="default", id=1)
        self.lab = G(Lab, name="ECCL")
        self.fake_study = G(Study, study_type=self.study_type, lab=self.lab)
        self.complex_condition = (
            "((deaf OR hearing_impairment) OR NOT speaks_en) "
            "AND "
            "(age_in_days >= 365 AND age_in_days <= 1095)"
        )
        self.malformed_condition = "deaf or hearing_impairment or multiple_birth"

        self.compound_or_condition = "deaf OR hearing_impairment OR multiple_birth"

        self.gestational_age_range_condition = (
            "gestational_age_in_weeks <= 28 AND gestational_age_in_weeks > 24"
        )

        self.unspecified_gestational_age_range_condition = (
            "gestational_age_in_weeks = na"
        )

        self.gender_specific_condition = "gender = male OR gender = OTHER"

        self.number_of_languages_condition = "num_languages < 6 AND n_languages > 1"

        self.compound_and_condition = "deaf AND dyslexia AND age_in_days >= 1000"

        self.deaf_male_child = G(
            Child,
            existing_conditions=Child.existing_conditions.deaf,
            gender="m",
            languages_spoken=Child.languages_spoken.en,
            birthday=datetime.date.today() - datetime.timedelta(days=3 * 365),
        )

        self.hearing_impaired_child = G(
            Child,
            existing_conditions=Child.existing_conditions.hearing_impairment,
            languages_spoken=Child.languages_spoken.en,
            birthday=datetime.date.today() - datetime.timedelta(days=3 * 365),
        )

        self.french_female_twin = G(
            Child,
            existing_conditions=Child.existing_conditions.multiple_birth,
            languages_spoken=Child.languages_spoken.fr,
            gender="f",
            birthday=datetime.date.today() - datetime.timedelta(days=3 * 365),
        )

        self.older_deaf_child_with_dyslexia = G(
            Child,
            existing_conditions=Child.existing_conditions.deaf
            | Child.existing_conditions.dyslexia,
            languages_spoken=Child.languages_spoken.en,
            birthday=datetime.date.today() - datetime.timedelta(days=10 * 365),
        )

        self.born_at_25_weeks = G(
            Child,
            gestational_age_at_birth=GESTATIONAL_AGE_CHOICES.twenty_five_weeks,
            birthday=datetime.date.today() - datetime.timedelta(days=3 * 365),
        )

        self.born_at_35_weeks = G(
            Child,
            gestational_age_at_birth=GESTATIONAL_AGE_CHOICES.thirty_five_weeks,
            birthday=datetime.date.today() - datetime.timedelta(days=3 * 365),
        )

        self.child_with_unspecified_gestational_age = G(
            Child,
            gestational_age_at_birth=GESTATIONAL_AGE_CHOICES.no_answer,
            birthday=datetime.date.today() - datetime.timedelta(days=3 * 365),
        )

        self.polyglot_child = G(
            Child,
            languages_spoken=Child.languages_spoken.en
            | Child.languages_spoken.fr
            | Child.languages_spoken.ja
            | Child.languages_spoken.nl
            | Child.languages_spoken.ko,
            birthday=datetime.date.today() - datetime.timedelta(days=3 * 365),
        )

    def test_simple_condition(self):
        self.assertTrue(get_child_eligibility(self.deaf_male_child, "deaf"))

    def test_complex_condition(self):
        self.assertTrue(
            get_child_eligibility(self.deaf_male_child, self.complex_condition)
        )
        self.assertTrue(
            get_child_eligibility(self.hearing_impaired_child, self.complex_condition)
        )
        self.assertTrue(
            get_child_eligibility(self.french_female_twin, self.complex_condition)
        )
        self.assertFalse(
            get_child_eligibility(
                self.older_deaf_child_with_dyslexia, self.complex_condition
            )
        )

    def test_parse_failure(self):
        self.assertRaises(
            UnexpectedCharacters,
            get_child_eligibility,
            self.deaf_male_child,
            self.malformed_condition,
        )

    def test_compound_or(self):
        self.assertTrue(
            get_child_eligibility(self.deaf_male_child, self.compound_or_condition)
        )
        self.assertTrue(
            get_child_eligibility(
                self.hearing_impaired_child, self.compound_or_condition
            )
        )
        # Non-english speaking also multiple birth
        self.assertTrue(
            get_child_eligibility(self.french_female_twin, self.compound_or_condition)
        )

    def test_compound_and(self):
        self.assertTrue(
            get_child_eligibility(
                self.older_deaf_child_with_dyslexia, self.compound_and_condition
            )
        )

        self.assertFalse(
            get_child_eligibility(self.french_female_twin, self.compound_and_condition)
        )

    def test_gestational_age_range(self):
        self.assertTrue(
            get_child_eligibility(
                self.born_at_25_weeks, self.gestational_age_range_condition
            )
        )

        self.assertFalse(
            get_child_eligibility(
                self.born_at_35_weeks, self.gestational_age_range_condition
            )
        )

    def test_gender_specification(self):
        self.assertTrue(
            get_child_eligibility(self.deaf_male_child, self.gender_specific_condition)
        )

        self.assertFalse(
            get_child_eligibility(
                self.french_female_twin, self.gender_specific_condition
            )
        )

    def test_num_languages_spoken(self):
        self.assertTrue(
            get_child_eligibility(
                self.polyglot_child, self.number_of_languages_condition
            )
        )

        self.assertFalse(
            get_child_eligibility(
                self.french_female_twin, self.number_of_languages_condition
            )
        )

    def test_unspecified_gestational_age(self):
        self.assertTrue(
            get_child_eligibility(
                self.child_with_unspecified_gestational_age,
                self.unspecified_gestational_age_range_condition,
            )
        )

        self.assertFalse(
            get_child_eligibility(
                self.child_with_unspecified_gestational_age,
                self.gestational_age_range_condition,
            )
        )
