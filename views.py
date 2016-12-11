from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template import loader
from django.urls import reverse

from cookbook.forms import AdvancedSearchForm, SaveSearchForm, \
    NutritionPreferenceForm
from cookbook.methods import *
from cookbook.models import Recipe, UserFavorite, SavedSearch, \
    NutritionPreference, Nutrient


def index(request):
    recipe_list = Recipe.objects.order_by('?')[:9]
    template = loader.get_template('cookbook/index.html')
    context = {'recipe_list': recipe_list}
    add_common_context(context)
    return HttpResponse(template.render(context, request))


def recipe_detail(request, recipe_id, error_message=None):
    recipe = get_object_or_404(Recipe, pk=recipe_id)
    recipe.instructions = recipe.instructions.replace("@newline@", "\n")
    context = {'recipe': recipe, 'error_message': error_message}

    # add favorite star
    if request.user.id:
        context["show_favorite_star"] = True
    try:
        UserFavorite.objects.get(user=request.user, recipe=recipe)
        context["favorite_star_filled"] = True
    except ObjectDoesNotExist:
        context["favorite_star_filled"] = False

    nutrients = {}
    context["nutrients"] = nutrients
    # add nutrition info
    for ri in recipe.recipeingredient_set.all():
        for nutritionpreference in request.user.nutritionpreference_set.all():
            nutrient = nutritionpreference.nutrient
            inn = ri.ingredient.ingredientnutrient_set.get(nutrient=nutrient)
            nid = inn.nutrient.id
            if str(nid) not in nutrients:
                nutrients[str(nid)] = {
                    'name': nutrient.name, 'unit': nutrient.unit,
                    'amount': 0}
            amount_per_recipe = inn.amount / 100 * ri.amount * ri.gram_mapping.amount_grams
            amount_per_serving = amount_per_recipe / recipe.serves
            nutrients[str(nid)]['amount'] += amount_per_serving

    # add other context
    add_common_context(context)
    template = loader.get_template('cookbook/recipe_detail.html')
    return HttpResponse(template.render(context, request))


@login_required
def favorite(request, recipe_id):
    recipe = get_object_or_404(Recipe, pk=recipe_id)
    try:
        user_favorite = UserFavorite.objects.get(user=request.user,
            recipe=recipe)
        user_favorite.delete()
    except UserFavorite.DoesNotExist:
        user_favorite = UserFavorite(user=request.user, recipe=recipe)
        user_favorite.save()

    args = {"recipe_id": recipe_id}
    return HttpResponseRedirect(reverse('cookbook:recipe_detail', kwargs=args))


def tag_search(request, tag):
    return HttpResponseRedirect(
        "/cookbook/advanced_search/?recipe_name_search_term=&ingredient_name_search_term=&tags=" + tag)


@login_required
def advanced_recipe_search(request):
    template = loader.get_template('cookbook/advanced_search.html')
    context = {'advanced_search_form': AdvancedSearchForm()}
    add_common_context(context)

    ingredient_name_search_term = request.GET.get("ingredient_name_search_term")
    recipe_name_search_term = request.GET.get("recipe_name_search_term")

    # need special handling for list-type parameters
    parameter_dictionary = dict(request.GET)
    if "tags" in parameter_dictionary:
        tags = parameter_dictionary["tags"]
    else:
        tags = []
    if "food_groups" in parameter_dictionary:
        food_groups = parameter_dictionary["food_groups"]
    else:
        food_groups = []

    if recipe_name_search_term or tags or food_groups or ingredient_name_search_term:
        search = create_saved_search(food_groups, ingredient_name_search_term,
            recipe_name_search_term, request, tags)
        params = {
            "ingredient_name_search_term": ingredient_name_search_term,
            "recipe_name_search_term": recipe_name_search_term, "tags": tags,
            "food_groups": food_groups}
        request.session["most_recent_search"] = params
        context['advanced_search_form'] = AdvancedSearchForm(initial=params)

        results = execute_saved_search(search)
        search.delete()
        print(results)

        # need to pass extra parameter to distinguish between 0 results and
        # didn't search yet
        if results:
            context["search_results"] = results
            # add save search form if there are results
            context["save_search_form"] = SaveSearchForm()
        else:
            context["no_matches"] = True

    return HttpResponse(template.render(context, request))


def save_search(request):
    most_recent_search_dict = request.session["most_recent_search"]
    if most_recent_search_dict:
        ingredient_name_search_term = most_recent_search_dict[
            "ingredient_name_search_term"]
        recipe_name_search_term = most_recent_search_dict[
            "recipe_name_search_term"]
        tags = most_recent_search_dict["tags"]
        food_groups = most_recent_search_dict["food_groups"]
        saved_search = create_saved_search(food_groups,
            ingredient_name_search_term, recipe_name_search_term, request, tags)
        saved_search.search_name = request.POST.get("saved_search_name")
        saved_search.save()
    return HttpResponseRedirect(reverse('cookbook:user_profile'))


def change_preferences(request):
    if request.method == 'POST':
        # delete existing preferences
        for pref in NutritionPreference.objects.filter(user=request.user):
            pref.delete()

        nutrients = dict(request.POST)["nutrients"]
        for nutrient_id in nutrients:
            nutrient = Nutrient.objects.get(pk=nutrient_id)
            preference = NutritionPreference(user=request.user,
                nutrient=nutrient)
            preference.save()
        return HttpResponseRedirect(reverse('cookbook:index'))
    else:
        params = {"nutrients": request.user.nutritionpreference_set.all()}
        form = NutritionPreferenceForm(initial=params)
        context = {"nutrition_preference_form": form}
        return render(request, 'cookbook/change_preferences.html', context)


def delete_saved_search(request, saved_search_id):
    saved_search = SavedSearch.objects.get(pk=saved_search_id)
    saved_search.delete()
    return HttpResponseRedirect(reverse('cookbook:user_profile'))


def create_user_account(request):
    return render(request, 'cookbook/create_user_account.html')


def saved_search_detail(request, saved_search_id):
    saved_search = get_object_or_404(SavedSearch, pk=saved_search_id)
    context = {'saved_search': saved_search}
    add_common_context(context)
    template = loader.get_template("cookbook/saved_search_detail.html")
    return HttpResponse(template.render(context, request))


def user_profile(request):
    template = loader.get_template('cookbook/user_profile.html')
    context = {}
    add_common_context(context)
    return HttpResponse(template.render(context, request))

# vim: autoindent tabstop=4 shiftwidth=4 expandtab softtabstop=4 filetype=python
