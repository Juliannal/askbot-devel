from askbot.tests.utils import AskbotTestCase
from askbot.conf import settings as askbot_settings
from askbot import forms
from askbot import models

EMAIL_CASES = (#test should fail if the second item is None
    ('user@example.com', 'user@example.com'),
    ('Name Name <name@example.com>', 'name@example.com'),
    ('"Name Name [example.com]" <name@example.com>', 'name@example.com'),
    (
        'someone <reply+m-4823355-3ae97f4698708d0be6bb087d6d4ce1e5e33ac131@reply.example.com>',
        'reply+m-4823355-3ae97f4698708d0be6bb087d6d4ce1e5e33ac131@reply.example.com'
    ),
    (
        'freddy krueger <someone@example.edu> (by way of somebody else)',
        'someone@example.edu'
    ),
    (
        'Google Anniversary Promotion =?iso-8859-1?Q?=A9_2011?= <someone@example.br>',
        'someone@example.br'
    ),
    ('=?koi8-r?B?5sHExcXXwSDvzNjHwQ==?= <someone@example.ru>', 'someone@example.ru'),
    ('root@example.org (Cron Daemon)', 'root@example.org'),
    ('<summary@example.com>', 'summary@example.com'),
    ('some text without an email adderess', None)
)
SUBJECT_LINE_CASES = (#test fails if second item is None
    (
        ' [ tag1;long  tag, another] question title',
        ('tag1 long-tag another', 'question title')
    ),
    ('[] question title', None),
    ('question title', None),
    ('   [question title', None),
    ('] question title', None),
)

class AskByEmailFormTests(AskbotTestCase):
    """Tests :class:`~askbot.forms.AskByEmailForm`
    form"""
    def setUp(self):
        #benign data set that must pass
        self.data = {
            'sender': 'someone@example.com',
            'subject': '[tag-one] where is titanic?',
            'body_text': 'where is titanic?'
        }
    def test_subject_line(self):
        """loops through various forms of the subject line
        and makes sure that tags and title are parsed out"""
        for test_case in SUBJECT_LINE_CASES:
            self.data['subject'] = test_case[0]
            form = forms.AskByEmailForm(self.data)
            output = test_case[1]
            if output is None:
                self.assertFalse(form.is_valid())
            else:
                self.assertTrue(form.is_valid())
                self.assertEquals(
                    form.cleaned_data['tagnames'],
                    output[0]
                )
                self.assertEquals(
                    form.cleaned_data['title'],
                    output[1]
                )

    def test_email(self):
        """loops through variants of the from field 
        in the emails and tests the email address 
        extractor"""
        for test_case in EMAIL_CASES:
            self.data['sender'] = test_case[0]
            expected_result = test_case[1]
            form = forms.AskByEmailForm(self.data)
            if expected_result is None:
                self.assertFalse(form.is_valid())
            else:
                self.assertTrue(form.is_valid())
                self.assertEquals(
                    form.cleaned_data['email'],
                    expected_result
                )

class TagNamesFieldTests(AskbotTestCase):

    def setUp(self):
        self.field = forms.TagNamesField()
        self.user = self.create_user('user1')

    def clean(self, value):
        return self.field.clean(value).strip().split(' ')

    def assert_tags_equal(self, tag_list1, tag_list2):
        self.assertEqual(sorted(tag_list1), sorted(tag_list2))

    def test_force_lowercase(self):
        """FORCE_LOWERCASE setting is on
        """
        askbot_settings.update('FORCE_LOWERCASE_TAGS', True)
        cleaned_tags = self.clean('Tag1 TAG5 tag1 tag5')
        self.assert_tags_equal(cleaned_tags, ['tag1','tag5'])

    def test_custom_case(self):
        """FORCE_LOWERCASE setting is off
        """
        askbot_settings.update('FORCE_LOWERCASE_TAGS', False)
        models.Tag(name = 'TAG1', created_by = self.user).save()
        models.Tag(name = 'Tag2', created_by = self.user).save()
        cleaned_tags = self.clean('tag1 taG2 TAG1 tag3 tag3')
        self.assert_tags_equal(cleaned_tags, ['TAG1', 'Tag2', 'tag3'])

class EditQuestionAnonymouslyFormTests(AskbotTestCase):
    """setup the following truth table
    on reveal_identity field:
    is_anon  can  owner  checked  result

    """
    truth_table = (
        (0, 0, 0, 0, False),
        (0, 0, 0, 1, False),
        (0, 0, 1, 0, False),
        (0, 0, 1, 1, False),
        (0, 1, 0, 0, False),
        (0, 1, 0, 1, False),
        (0, 1, 1, 0, False),
        (0, 1, 1, 1, False),#all up to this point are False
        (1, 0, 0, 0, False),
        (1, 0, 0, 1, 'error'),#not owner
        (1, 0, 1, 0, 'error'),#rules changed either reload page or check box
        (1, 0, 1, 1, True),#rules changed - say yes here
        (1, 1, 0, 0, False),
        (1, 1, 0, 1, 'error'),
        (1, 1, 1, 0, False),
        (1, 1, 1, 1, True),
    )
    #legend: is_anon - question is anonymous
    #        can - askbot_settings.ALLOW_ASK_ANONYMOUSLY
    #        owner - editor is question owner
    #        checked - the checkbox "reveal_identity" is marked
    def setUp(self):
        self.create_user()
        self.create_user(
            username = 'other_user',
            status = 'm'#must be able to edit
        )
        super(EditQuestionAnonymouslyFormTests, self).setUp()

    def setup_data(self, is_anon, can_be_anon, is_owner, box_checked):
        """sets up data in the same order as shown in the
        truth table above
        
        the four positional arguments are in the same order
        """
        askbot_settings.update('ALLOW_ASK_ANONYMOUSLY', can_be_anon)
        question = self.post_question(is_anonymous = is_anon)
        if is_owner:
            editor = self.user
        else:
            editor = self.other_user
        data = {
            'tags': 'tag1 tag2',
            'text': 'ostaousohuosuh',
            'title': 'stahosetuhaoeudhuh'
        }
        if box_checked:
            data['reveal_identity'] = 'on'
        self.form = forms.EditQuestionForm(
                        data,
                        question = question,
                        user = editor,
                        revision = question.get_latest_revision(),
                    )

    def test_reveal_identity_field(self):
        """runs through the truth table and tests them items by one
        """
        current_item = 0
        for entry in self.truth_table:
            self.setup_data(*(entry[:4]))

            if self.form.is_valid():
                result = self.form.cleaned_data['reveal_identity']
            else:
                result = 'error'

            error_message = 'failed truth table item %d' % current_item
            current_item += 1

            expected_result = entry[4]
            self.assertEquals(result, expected_result, error_message)

class AskFormTests(AskbotTestCase):

    def setup_data(self, allow_anonymous = True, ask_anonymously = None):
        askbot_settings.update('ALLOW_ASK_ANONYMOUSLY', allow_anonymous)
        data = {
            'title': 'test title',
            'text': 'test content',
            'tags': 'test',
        }
        if ask_anonymously == True:
            data['ask_anonymously'] = 'on'
        self.form = forms.AskForm(data)
        self.form.full_clean()

    def assert_anon_is(self, value):
        self.assertEquals(
            self.form.cleaned_data['ask_anonymously'],
            value
        )

    def test_ask_anonymously_disabled(self):
        """test that disabled anon postings yields False"""
        self.setup_data(ask_anonymously = True, allow_anonymous = False)
        self.assert_anon_is(False)

    def test_ask_anonymously_field_positive(self):
        """check that the 'yes' selection goes through
        """
        self.setup_data(ask_anonymously = True)
        self.assert_anon_is(True)
    
    def test_ask_anonymously_field_negative(self):
        """check that the 'no' selection goes through
        """
        self.setup_data(ask_anonymously = False)
        self.assert_anon_is(False)
