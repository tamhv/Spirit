import datetime

from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone

from spirit.core.tests import utils
from . import views as category_views
from spirit.category.models import Category
from .forms import CategoryForm

User = get_user_model()


class AdminViewTest(TestCase):

    def setUp(self):
        utils.cache_clear()
        self.user = utils.create_user()
        self.user.st.is_administrator = True
        self.user.st.save()
        self.category = utils.create_category()
        self.topic = utils.create_topic(self.category, user=self.user)

    def test_permission_denied_to_non_admin(self):
        req = RequestFactory().get('/')
        req.user = self.user
        req.user.st.is_administrator = False

        self.assertRaises(PermissionDenied, category_views.index, req)
        self.assertRaises(PermissionDenied, category_views.create, req)
        self.assertRaises(PermissionDenied, category_views.update, req)

    def test_category_list(self):
        """
        Categories, excludes Topic Private and subcats
        """
        utils.create_category(parent=self.category)
        categories = Category.objects.filter(is_private=False, parent=None)
        utils.login(self)
        response = self.client.get(reverse('spirit:admin:category:index'))
        self.assertEqual(list(response.context['categories']), list(categories))

    def test_category_create(self):
        """
        Category create
        """
        utils.login(self)
        form_data = {
            "parent": "", "title": "foo", "description": "",
            "is_closed": False, "is_removed": False, "is_global": True, "color": ""}
        response = self.client.post(reverse('spirit:admin:category:create'),
                                    form_data)
        expected_url = reverse("spirit:admin:category:index")
        self.assertRedirects(response, expected_url, status_code=302)

        response = self.client.get(reverse('spirit:admin:category:create'))
        self.assertEqual(response.status_code, 200)

    def test_category_update(self):
        """
        Category update
        """
        utils.login(self)
        form_data = {
            "parent": "", "title": "foo", "description": "",
            "is_closed": False, "is_removed": False, "is_global": True, "color": "#ff0000"}
        response = self.client.post(
            reverse('spirit:admin:category:update', kwargs={"category_id": self.category.pk, }),
            form_data)
        expected_url = reverse("spirit:admin:category:index")
        self.assertRedirects(response, expected_url, status_code=302)

        response = self.client.get(
            reverse('spirit:admin:category:update', kwargs={"category_id": self.category.pk, }))
        self.assertEqual(response.status_code, 200)

    def test_category_form_color(self):
        """ Test category form raises exception on wrong color """
        form_data = {
            "parent": "", "title": "foo", "description": "",
            "is_closed": False, "is_removed": False, "is_global": True, "color": "#QWERTZ"}
        form = CategoryForm(data=form_data)

        self.assertFalse(form.is_valid())

    def test_category_move_up_down(self):
        """Should order the category when moving up/down"""
        utils.login(self)
        self.another_category = utils.create_category()
        response = self.client.post(
            reverse(
                'spirit:admin:category:move_dn',
                kwargs={"category_id": self.category.pk, }))
        expected_url = reverse("spirit:admin:category:index")
        self.assertRedirects(response, expected_url, status_code=302)
        self.category.refresh_from_db()
        self.another_category.refresh_from_db()        
        self.assertTrue(self.category.sort > self.another_category.sort)

        response = self.client.post(
            reverse(
                'spirit:admin:category:move_up',
                kwargs={"category_id": self.category.pk, }))
        expected_url = reverse("spirit:admin:category:index")
        self.assertRedirects(response, expected_url, status_code=302)
        self.category.refresh_from_db()
        self.another_category.refresh_from_db()        
        self.assertTrue(self.category.sort < self.another_category.sort)


class AdminFormTest(TestCase):

    def setUp(self):
        utils.cache_clear()
        self.user = utils.create_user()
        self.category = utils.create_category()
        self.topic = utils.create_topic(self.category)

    def test_category(self):
        """
        Add category
        """
        form_data = {
            "parent": "",
            "title": "foo",
            "description": "",
            "is_closed": False,
            "is_removed": False,
            "is_global": True,
            "color": ""
        }
        form = CategoryForm(data=form_data)
        self.assertEqual(form.is_valid(), True)
        category = form.save()
        self.assertTrue(category.sort > 0)

    def test_category_invalid_parent(self):
        """
        invalid parent
        """
        # parent can not be a subcategory, only one level subcat is allowed
        subcategory = utils.create_category(parent=self.category)
        form_data = {"parent": subcategory.pk, }
        form = CategoryForm(data=form_data)
        self.assertEqual(form.is_valid(), False)
        self.assertNotIn('parent', form.cleaned_data)

        # parent can not be set to a category with childrens
        category_ = utils.create_category()
        form_data = {"parent": category_.pk, }
        form = CategoryForm(data=form_data, instance=self.category)
        self.assertEqual(form.is_valid(), False)
        self.assertNotIn('parent', form.cleaned_data)

        # parent can not be removed
        category_ = utils.create_category(is_removed=True)
        form_data = {"parent": category_.pk, }
        form = CategoryForm(data=form_data)
        self.assertEqual(form.is_valid(), False)
        self.assertNotIn('parent', form.cleaned_data)

        # parent can not be private
        category_ = utils.create_category(is_private=True)
        form_data = {"parent": category_.pk, }
        form = CategoryForm(data=form_data)
        self.assertEqual(form.is_valid(), False)
        self.assertNotIn('parent', form.cleaned_data)

    def test_category_updates_reindex_at(self):
        """
        Should update reindex_at field
        """
        form_data = {
            "parent": "",
            "title": "foo",
            "description": "",
            "is_closed": False,
            "is_removed": False,
            "is_global": True,
            "color": ""}
        yesterday = timezone.now() - datetime.timedelta(days=1)
        category = utils.create_category(
            reindex_at=yesterday)
        self.assertEqual(
            category.reindex_at,
            yesterday)
        form = CategoryForm(instance=category, data=form_data)
        self.assertEqual(form.is_valid(), True)
        form.save()
        self.assertGreater(
            Category.objects.get(pk=category.pk).reindex_at,
            yesterday)

    @override_settings(ST_ORDERED_CATEGORIES=True)
    def test_category_order(self):
        Category.objects.all().delete()
        cat1 = utils.create_category(title="1", sort=2)
        cat2 = utils.create_category(title="2", sort=1)
        self.assertEqual(list(Category.objects.all()), [cat1, cat2])
        form = CategoryForm(data=None)
        self.assertEqual(list(form.fields['parent'].queryset), [cat2, cat1])
        cat1.sort = 0
        cat1.save()
        self.assertEqual(list(Category.objects.all()), [cat1, cat2])
        form = CategoryForm(data=None)
        self.assertEqual(list(form.fields['parent'].queryset), [cat1, cat2])

    @override_settings(ST_ORDERED_CATEGORIES=False)
    def test_category_order_by_title(self):
        Category.objects.all().delete()
        cat1 = utils.create_category(title="1", sort=2)
        cat2 = utils.create_category(title="2", sort=1)
        self.assertEqual(list(Category.objects.all()), [cat1, cat2])
        form = CategoryForm(data=None)
        self.assertEqual(list(form.fields['parent'].queryset), [cat1, cat2])
