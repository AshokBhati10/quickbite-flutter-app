"""Repeatable seed: accounts, 25 restaurants with categorized menus, drivers.

Run:  .venv/bin/python scripts/seed.py
Safe to run twice: upserts by primary key, so repeated runs refresh the
catalog in place instead of creating duplicates, and never delete rows.

Architecture:
  * LEGACY holds the original restaurants/menu items verbatim, so their ids,
    prices and relationships (and therefore order history) are preserved.
  * MENUS holds per-cuisine menu templates; GENERATED restaurant specs reuse
    a template and get item ids derived from the restaurant id. Adding more
    restaurants is a data edit only -- no code or schema change -- so the
    catalog scales past 50 with the same generator.

Images are stable, openly licensed references (Wikimedia Commons restaurant
photos and TheMealDB food photos); the web client renders them with a graceful
fallback when a URL cannot load. No category/image data is inferred: cuisine,
category and image_url are first-class columns.
"""

from __future__ import annotations

import asyncio
import os
import sys

for _candidate in (
    os.path.join(os.path.dirname(__file__), "..", "backend"),
    "/srv/app",
):
    if os.path.isdir(os.path.join(_candidate, "app")):
        sys.path.insert(0, _candidate)

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import init_db, session_factory  # noqa: E402
from app.domain.auth import hash_password  # noqa: E402
from app.domain.models import Driver, MenuItem, Restaurant, User  # noqa: E402

PASSWORD = os.environ.get("SEED_PASSWORD", "Password123!")

USERS = (
    dict(id="user_customer", email="customer@quickbite.test", role="customer", name="Demo Customer"),
    dict(id="user_admin", email="admin@quickbite.test", role="admin", name="Demo Admin"),
)

DRIVERS = (
    dict(id="driver_1", name="Asha Kumar"),
    dict(id="driver_2", name="Ravi Singh"),
    dict(id="driver_3", name="Meera Nair"),
    dict(id="driver_4", name="Sameer Khan"),
)

CATEGORY_ORDER = ("Starters", "Main Course", "Sides", "Beverages", "Desserts")

# --------------------------------------------------------------------------
# Images: stable, openly licensed, CORS-enabled. Restaurant covers are
# Wikimedia Commons dining-room photos; food photos are TheMealDB media
# (starters/mains/sides/desserts) and Commons (beverages). Assign by index so
# 50+ restaurants can reuse the pool without any architectural change.
# --------------------------------------------------------------------------
RESTAURANT_IMAGES = (
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ae/Caesar%27s_restaurant_interior_2019.jpg/960px-Caesar%27s_restaurant_interior_2019.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b4/Childs%27_Restaurant_building_interior_%2884200%29.jpg/960px-Childs%27_Restaurant_building_interior_%2884200%29.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c9/Empty_restaurant_interior_HC08164.jpg/960px-Empty_restaurant_interior_HC08164.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f9/Restaurant_in_Place_D%27Youville%2C_Quebec_City.jpg/960px-Restaurant_in_Place_D%27Youville%2C_Quebec_City.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/1d/Restaurant_in_The_Mus%C3%A9e_d%27Orsay.jpg/960px-Restaurant_in_The_Mus%C3%A9e_d%27Orsay.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/5f/Restaurant_interior%2C_Paris.jpg/960px-Restaurant_interior%2C_Paris.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/07/Restaurant_interior%2C_The_Riverhead.jpg/960px-Restaurant_interior%2C_The_Riverhead.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f3/Restaurant_room_of_Amantaka_luxury_Resort_%26_Hotel_in_Luang_Prabang_Laos.jpg/960px-Restaurant_room_of_Amantaka_luxury_Resort_%26_Hotel_in_Luang_Prabang_Laos.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/3/33/The_Peninsula_Paris%27_Chinese_restaurant_LiLi%2C_12_August_2014.jpg/960px-The_Peninsula_Paris%27_Chinese_restaurant_LiLi%2C_12_August_2014.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/9b/20090121_Pizzeria_Italia_Groningen_NL.jpg/960px-20090121_Pizzeria_Italia_Groningen_NL.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b5/Brozinni_Pizzeria_-_October_2023_-_Sarah_Stierch_03.jpg/960px-Brozinni_Pizzeria_-_October_2023_-_Sarah_Stierch_03.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/78/Brozinni_Pizzeria_Speedway_-_June_2022_-_Sarah_Stierch_02.jpg/960px-Brozinni_Pizzeria_Speedway_-_June_2022_-_Sarah_Stierch_02.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/de/Cafe_Deco_Pizzeria_Interior_Photo.jpg/960px-Cafe_Deco_Pizzeria_Interior_Photo.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a6/Ennis_-_3_Barrack_Street_-_Numero_Uno_Pizzeria_Interior_-_geograph.org.uk_-_3070065.jpg/960px-Ennis_-_3_Barrack_Street_-_Numero_Uno_Pizzeria_Interior_-_geograph.org.uk_-_3070065.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/62/Interior_of_Sergio%E2%80%99s_al_Mare_pizzeria_at_Turku_Boatyard.jpg/960px-Interior_of_Sergio%E2%80%99s_al_Mare_pizzeria_at_Turku_Boatyard.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/ce/Italian_Pizzeria_and_Restaurant_interior%2C_Live_Oak.jpg/960px-Italian_Pizzeria_and_Restaurant_interior%2C_Live_Oak.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/75/Miracle_Pizzeria_-_02.jpg/960px-Miracle_Pizzeria_-_02.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f6/Pizzeria_%22Nu_Parrinaru%22%2C_Partinico.jpg/960px-Pizzeria_%22Nu_Parrinaru%22%2C_Partinico.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/8/80/Pizzeria_%282103513070%29.jpg/960px-Pizzeria_%282103513070%29.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f4/Cafe_Interior_-_geograph.org.uk_-_4801988.jpg/960px-Cafe_Interior_-_geograph.org.uk_-_4801988.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6d/Cafe_Muji_Shinjuku_Store_Interior_2013.jpg/960px-Cafe_Muji_Shinjuku_Store_Interior_2013.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e1/Cafe_interior_-_geograph.org.uk_-_4801991.jpg/960px-Cafe_interior_-_geograph.org.uk_-_4801991.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/64/Gundam_Cafe_Interior_Shot_A.jpg/960px-Gundam_Cafe_Interior_Shot_A.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/14/Interior_of_1UP_Cafe_2024-02-18.jpg/960px-Interior_of_1UP_Cafe_2024-02-18.jpg",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d4/Starmugs_Cafe_interior_on_Lordship_Lane_Tottenham_London_England_02.jpg/960px-Starmugs_Cafe_interior_on_Lordship_Lane_Tottenham_London_England_02.jpg",
)

CATEGORY_IMAGES = {
    "Starters": (
        "https://www.themealdb.com/images/media/meals/5jdtie1763289302.jpg",
        "https://www.themealdb.com/images/media/meals/fg7d641784666908.jpg",
        "https://www.themealdb.com/images/media/meals/tvvxpv1511191952.jpg",
        "https://www.themealdb.com/images/media/meals/rvtvuw1511190488.jpg",
        "https://www.themealdb.com/images/media/meals/stpuws1511191310.jpg",
        "https://www.themealdb.com/images/media/meals/oemdp11779556068.jpg",
        "https://www.themealdb.com/images/media/meals/0r7y5n1782681336.jpg",
        "https://www.themealdb.com/images/media/meals/7whfgi1782678933.jpg",
    ),
    "Main Course": (
        "https://www.themealdb.com/images/media/meals/9ya6o71780262651.jpg",
        "https://www.themealdb.com/images/media/meals/sbx7n71587673021.jpg",
        "https://www.themealdb.com/images/media/meals/syqypv1486981727.jpg",
        "https://www.themealdb.com/images/media/meals/uuuspp1511297945.jpg",
        "https://www.themealdb.com/images/media/meals/wruvqv1511880994.jpg",
        "https://www.themealdb.com/images/media/meals/qxytrx1511304021.jpg",
        "https://www.themealdb.com/images/media/meals/qtuwxu1468233098.jpg",
        "https://www.themealdb.com/images/media/meals/vdwloy1713225718.jpg",
    ),
    "Sides": (
        "https://www.themealdb.com/images/media/meals/grhn401765687086.jpg",
        "https://www.themealdb.com/images/media/meals/sr7chd1780264758.jpg",
        "https://www.themealdb.com/images/media/meals/5vhbzt1782239221.jpg",
        "https://www.themealdb.com/images/media/meals/j223gc1784579841.jpg",
        "https://www.themealdb.com/images/media/meals/qywups1511796761.jpg",
        "https://www.themealdb.com/images/media/meals/sl7cr91782588539.jpg",
        "https://www.themealdb.com/images/media/meals/dlmh401760524897.jpg",
        "https://www.themealdb.com/images/media/meals/o2cd4r1764113576.jpg",
    ),
    "Beverages": (
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e8/15-09-26-RalfR-WLC-0098_-_Coca-Cola_glass_bottle_%28Germany%29.jpg/960px-15-09-26-RalfR-WLC-0098_-_Coca-Cola_glass_bottle_%28Germany%29.jpg",
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/10/Glass_cola.jpg/960px-Glass_cola.jpg",
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/01/Classic_glass_bottle_of_T%C5%99eb%C3%AD%C4%8D_ZON_apple_lemonade_in_T%C5%99eb%C3%AD%C4%8D%2C_T%C5%99eb%C3%AD%C4%8D_District.jpg/960px-Classic_glass_bottle_of_T%C5%99eb%C3%AD%C4%8D_ZON_apple_lemonade_in_T%C5%99eb%C3%AD%C4%8D%2C_T%C5%99eb%C3%AD%C4%8D_District.jpg",
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/19/Drink-glass-theme-summer-bubles_%2824242969381%29.jpg/960px-Drink-glass-theme-summer-bubles_%2824242969381%29.jpg",
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/8/85/Sparkling_drink_with_lemon_slice_in_tall_glass.jpg/960px-Sparkling_drink_with_lemon_slice_in_tall_glass.jpg",
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e4/Woman_holds_a_glass_of_drink_with_lime_and_mint_in_a_bright_indoor_setting.jpg/960px-Woman_holds_a_glass_of_drink_with_lime_and_mint_in_a_bright_indoor_setting.jpg",
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d0/Glass_cup_of_beverage_%28Unsplash%29.jpg/960px-Glass_cup_of_beverage_%28Unsplash%29.jpg",
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/93/Frugo_drinks_3.jpg/960px-Frugo_drinks_3.jpg",
    ),
    "Desserts": (
        "https://www.themealdb.com/images/media/meals/wkhg581762773124.jpg",
        "https://www.themealdb.com/images/media/meals/a4kgf21763075288.jpg",
        "https://www.themealdb.com/images/media/meals/q47rkb1762324620.jpg",
        "https://www.themealdb.com/images/media/meals/adxcbq1619787919.jpg",
        "https://www.themealdb.com/images/media/meals/xvsurr1511719182.jpg",
        "https://www.themealdb.com/images/media/meals/c0gmo31766594751.jpg",
        "https://www.themealdb.com/images/media/meals/wxywrq1468235067.jpg",
        "https://www.themealdb.com/images/media/meals/stnxzp1784835840.jpg",
    ),
}


def _item(name, category, description, price_minor, is_active=True):
    return dict(
        name=name,
        category=category,
        description=description,
        price_minor=price_minor,
        is_active=is_active,
    )


# --------------------------------------------------------------------------
# Original restaurants: ids, names, item ids, prices and availability kept
# exactly as before so existing orders/history remain valid.
# --------------------------------------------------------------------------
LEGACY = (
    dict(
        id="rest_spice", name="Spice Route", cuisine="North Indian",
        description="Aromatic biryanis, rich curries and North Indian classics.",
        items=(
            dict(id="item_biryani", **_item("Chicken Biryani", "Main Course", "Fragrant basmati layered with spiced chicken and saffron.", 1250)),
            dict(id="item_lassi", **_item("Mango Lassi", "Beverages", "Chilled yoghurt blended with Alphonso mango.", 400)),
            dict(id="item_kebab", **_item("Seekh Kebab (sold out)", "Starters", "Char-grilled minced lamb skewers with mint chutney.", 900, False)),
            dict(id="item_paneer_tikka", **_item("Paneer Tikka", "Starters", "Smoky cottage cheese marinated in yoghurt and spices.", 850)),
            dict(id="item_butter_chicken", **_item("Butter Chicken", "Main Course", "Tandoori chicken simmered in a silky tomato-butter gravy.", 1450)),
            dict(id="item_dal_makhani", **_item("Dal Makhani", "Main Course", "Black lentils slow-cooked overnight with cream.", 950)),
            dict(id="item_garlic_naan", **_item("Garlic Naan", "Sides", "Tandoor-baked flatbread brushed with garlic butter.", 300)),
            dict(id="item_jeera_rice", **_item("Jeera Rice", "Sides", "Basmati tossed with cumin and fried onion.", 350)),
            dict(id="item_gulab_jamun", **_item("Gulab Jamun", "Desserts", "Warm milk dumplings soaked in rose-cardamom syrup.", 400)),
            dict(id="item_masala_chai", **_item("Masala Chai", "Beverages", "Spiced black tea brewed with ginger and cardamom.", 250)),
        ),
    ),
    dict(
        id="rest_pasta", name="Pasta Basta", cuisine="Italian",
        description="Hand-rolled pasta, wood-fired pizzas and Italian comfort food.",
        items=(
            dict(id="item_pasta", **_item("Alfredo Pasta", "Main Course", "Fettuccine tossed in a creamy parmesan sauce.", 1100)),
            dict(id="item_pizza", **_item("Margherita Pizza", "Main Course", "Wood-fired dough with san marzano, basil and mozzarella.", 1500)),
            dict(id="item_bruschetta", **_item("Tomato Bruschetta", "Starters", "Toasted sourdough with marinated tomatoes and basil.", 700)),
            dict(id="item_garlic_bread", **_item("Cheesy Garlic Bread", "Sides", "Baked baguette with garlic butter and mozzarella.", 550)),
            dict(id="item_arrabbiata", **_item("Penne Arrabbiata", "Main Course", "Penne in a spicy garlic-chilli tomato sauce.", 1150)),
            dict(id="item_caesar_salad", **_item("Caesar Salad", "Sides", "Cos lettuce, croutons and parmesan in caesar dressing.", 800)),
            dict(id="item_tiramisu", **_item("Tiramisu", "Desserts", "Espresso-soaked ladyfingers with mascarpone cream.", 650)),
            dict(id="item_lemonade", **_item("Sicilian Lemonade", "Beverages", "Sparkling lemonade with mint and a hint of basil.", 350)),
        ),
    ),
    dict(
        id="rest_wok", name="Dragon Wok", cuisine="Chinese",
        description="Sizzling Indo-Chinese wok specials, noodles and dumplings.",
        items=(
            dict(id="item_chilli_paneer", **_item("Chilli Paneer", "Starters", "Crispy paneer tossed with peppers in a spicy soy glaze.", 800)),
            dict(id="item_spring_rolls", **_item("Veg Spring Rolls", "Starters", "Crisp rolls stuffed with julienned garden vegetables.", 600)),
            dict(id="item_manchow_soup", **_item("Manchow Soup", "Starters", "Spiced soup topped with crispy noodles.", 450)),
            dict(id="item_dumplings", **_item("Steamed Chicken Dumplings", "Starters", "Juicy dumplings served with a chilli-soy dip.", 750)),
            dict(id="item_hakka_noodles", **_item("Chicken Hakka Noodles", "Main Course", "Stir-fried noodles with chicken, egg and spring onion.", 1050)),
            dict(id="item_fried_rice", **_item("Burnt Garlic Fried Rice", "Main Course", "Wok-tossed rice with roasted garlic and scallion.", 900)),
            dict(id="item_chilli_chicken", **_item("Chilli Chicken", "Main Course", "Crispy chicken in a fiery Sichuan-style sauce.", 1200)),
            dict(id="item_honey_potato", **_item("Honey Chilli Potato", "Sides", "Crisp potato batons in a sweet-hot sesame glaze.", 650)),
            dict(id="item_ice_cream", **_item("Vanilla Bean Ice Cream", "Desserts", "Slow-churned vanilla with a caramel swirl.", 350)),
            dict(id="item_iced_tea", **_item("Lemon Iced Tea", "Beverages", "Chilled black tea with lemon and orange.", 300)),
        ),
    ),
    dict(
        id="rest_burger", name="Burger Barn", cuisine="American",
        description="Flame-grilled burgers, loaded fries and thick shakes.",
        items=(
            dict(id="item_chicken_burger", **_item("Crispy Chicken Burger", "Main Course", "Buttermilk-fried chicken with pickles and smoky mayo.", 1250)),
            dict(id="item_veg_burger", **_item("Veggie Crunch Burger", "Main Course", "Spiced potato-bean patty with cheddar and slaw.", 1050)),
            dict(id="item_wings", **_item("Buffalo Chicken Wings", "Starters", "Sticky hot wings served with a blue-cheese dip.", 950)),
            dict(id="item_onion_rings", **_item("Onion Rings", "Sides", "Golden beer-battered onion rings.", 550)),
            dict(id="item_cheese_fries", **_item("Loaded Cheese Fries", "Sides", "Skin-on fries smothered in cheese sauce and jalapenos.", 650)),
            dict(id="item_coleslaw", **_item("House Coleslaw", "Sides", "Crunchy cabbage and carrot in a tangy dressing.", 350)),
            dict(id="item_choc_shake", **_item("Chocolate Thick Shake", "Beverages", "Blended Belgian chocolate with vanilla ice cream.", 500)),
            dict(id="item_cola", **_item("Chilled Cola", "Beverages", "Classic cola served over ice.", 200)),
            dict(id="item_brownie", **_item("Fudge Brownie Sundae", "Desserts", "Warm brownie with vanilla ice cream and fudge.", 600)),
        ),
    ),
    dict(
        id="rest_green", name="Green Bowl", cuisine="Healthy",
        description="Fresh salads, grain bowls and cold-pressed juices.",
        items=(
            dict(id="item_quinoa_bowl", **_item("Quinoa Power Bowl", "Main Course", "Quinoa, roasted veg and chickpeas with tahini drizzle.", 950)),
            dict(id="item_buddha_bowl", **_item("Buddha Bowl", "Main Course", "Brown rice, avocado and greens with miso dressing.", 900)),
            dict(id="item_hummus_pita", **_item("Hummus & Pita", "Starters", "Creamy chickpea hummus with warm whole-wheat pita.", 600)),
            dict(id="item_tomato_soup", **_item("Roasted Tomato Soup", "Starters", "Slow-roasted tomatoes with basil and a swirl of cream.", 450)),
            dict(id="item_greek_salad", **_item("Greek Salad", "Sides", "Cucumber, olives and feta with oregano vinaigrette.", 750)),
            dict(id="item_berry_smoothie", **_item("Berry Smoothie", "Beverages", "Mixed berries, banana and yoghurt with no added sugar.", 500)),
            dict(id="item_green_juice", **_item("Cold-Pressed Green Juice", "Beverages", "Apple, cucumber, spinach, ginger and lime.", 450)),
            dict(id="item_chia_pudding", **_item("Chia Seed Pudding", "Desserts", "Overnight chia in almond milk topped with mango.", 400)),
            dict(id="item_oat_cookie", **_item("Oat & Raisin Cookie", "Desserts", "Chewy wholegrain cookie with raisins and cinnamon.", 300)),
        ),
    ),
    dict(
        id="rest_coastal", name="Coastal Catch", cuisine="Seafood",
        description="Coastal seafood, fish curries and fragrant rice bowls.",
        items=(
            dict(id="item_fish_curry", **_item("Malabar Fish Curry", "Main Course", "Seer fish simmered in coconut and kokum.", 1400)),
            dict(id="item_prawn_pulao", **_item("Prawn Pulao", "Main Course", "Basmati cooked with prawns and warm coastal spices.", 1250)),
            dict(id="item_coastal_rice_bowl", **_item("Coastal Rice Bowl", "Main Course", "Fish curry over steamed red rice with pickles.", 1000)),
            dict(id="item_tandoori_prawns", **_item("Tandoori Prawns", "Starters", "Jumbo prawns in a smoky yoghurt marinade.", 1350)),
            dict(id="item_fish_fry", **_item("Amritsari Fish Fry", "Starters", "Crisp gram-flour battered river fish with lime.", 1100)),
            dict(id="item_calamari", **_item("Crispy Calamari", "Starters", "Lightly fried squid rings with garlic aioli.", 900, False)),
            dict(id="item_lemon_rice", **_item("Lemon Rice", "Sides", "Turmeric rice with peanuts and curry leaf.", 400)),
            dict(id="item_kokum_soda", **_item("Kokum Cooler", "Beverages", "Tangy kokum with cumin and mint.", 300)),
            dict(id="item_filter_coffee", **_item("Filter Coffee", "Beverages", "South-Indian decoction with frothy milk.", 250)),
            dict(id="item_payasam", **_item("Semiya Payasam", "Desserts", "Vermicelli pudding with cardamom and cashews.", 400)),
        ),
    ),
    dict(
        id="rest_sweet", name="Sweet Tooth", cuisine="Desserts",
        description="Cakes, pastries, waffles and artisanal desserts.",
        items=(
            dict(id="item_death_chocolate", **_item("Death by Chocolate", "Desserts", "Layered chocolate cake with ganache and mousse.", 700)),
            dict(id="item_red_velvet", **_item("Red Velvet Pastry", "Desserts", "Cream-cheese frosting on a cocoa sponge.", 550)),
            dict(id="item_cheesecake", **_item("New York Cheesecake", "Desserts", "Baked vanilla cheesecake with berry compote.", 650)),
            dict(id="item_macaron", **_item("Assorted Macarons", "Desserts", "Box of six almond macarons in seasonal flavours.", 800, False)),
            dict(id="item_waffle", **_item("Belgian Waffle", "Desserts", "Crisp waffle with chocolate sauce and berries.", 600)),
            dict(id="item_apple_pie", **_item("Cinnamon Apple Pie", "Desserts", "Buttery shortcrust filled with spiced apples.", 500)),
            dict(id="item_hot_chocolate", **_item("Belgian Hot Chocolate", "Beverages", "Rich dark chocolate steamed with milk.", 400)),
            dict(id="item_cold_coffee", **_item("Frappe Cold Coffee", "Beverages", "Blended coffee with ice cream and cocoa.", 450)),
        ),
    ),
    dict(
        id="rest_breakfast", name="The Breakfast Club", cuisine="Cafe & Breakfast",
        description="All-day breakfast, pancakes, eggs and fresh brews.",
        items=(
            dict(id="item_pancakes", **_item("Blueberry Pancakes", "Main Course", "Fluffy buttermilk pancakes with blueberry compote.", 700)),
            dict(id="item_omelette", **_item("Three-Cheese Omelette", "Main Course", "Fluffy omelette with cheddar, mozzarella and herbs.", 650)),
            dict(id="item_avocado_toast", **_item("Avocado Toast", "Starters", "Sourdough, smashed avocado, chilli flakes and lime.", 600)),
            dict(id="item_hash_browns", **_item("Crispy Hash Browns", "Sides", "Golden shredded potato cakes.", 350)),
            dict(id="item_sourdough_toast", **_item("Buttered Sourdough Toast", "Sides", "Thick-cut sourdough with cultured butter.", 250)),
            dict(id="item_orange_juice", **_item("Fresh Orange Juice", "Beverages", "Cold-pressed valencia oranges.", 350)),
            dict(id="item_cappuccino", **_item("Cappuccino", "Beverages", "Double espresso with velvety steamed milk.", 300)),
            dict(id="item_banana_bread", **_item("Banana Walnut Bread", "Desserts", "Moist banana loaf with toasted walnuts.", 400)),
            dict(id="item_granola", **_item("Yoghurt & Granola Parfait", "Desserts", "Greek yoghurt layered with honey granola and berries.", 450)),
        ),
    ),
)

# --------------------------------------------------------------------------
# Per-cuisine menu templates reused by generated restaurants. Each template
# covers all five categories so every restaurant has a varied menu.
# --------------------------------------------------------------------------
MENUS = {
    "north_indian": (
        _item("Paneer Tikka", "Starters", "Smoky cottage cheese in a spiced yoghurt marinade.", 850),
        _item("Chicken Malai Tikka", "Starters", "Creamy char-grilled chicken skewers.", 950),
        _item("Butter Chicken", "Main Course", "Tandoori chicken in a silky tomato-butter gravy.", 1450),
        _item("Dal Makhani", "Main Course", "Black lentils slow-cooked with cream.", 950),
        _item("Rogan Josh", "Main Course", "Kashmiri lamb curry with warm spices.", 1550, False),
        _item("Garlic Naan", "Sides", "Tandoor-baked flatbread with garlic butter.", 300),
        _item("Jeera Rice", "Sides", "Basmati tossed with cumin and fried onion.", 350),
        _item("Gulab Jamun", "Desserts", "Warm milk dumplings in rose syrup.", 400),
        _item("Masala Chai", "Beverages", "Spiced tea with ginger and cardamom.", 250),
    ),
    "south_indian": (
        _item("Medu Vada", "Starters", "Crisp lentil doughnuts with coconut chutney.", 400),
        _item("Mini Idli", "Starters", "Steamed rice cakes in sambar.", 350),
        _item("Masala Dosa", "Main Course", "Crisp crepe with spiced potato filling.", 600),
        _item("Curd Rice", "Main Course", "Comforting yoghurt rice with tempered spices.", 450),
        _item("Sambar Vada", "Main Course", "Vada soaked in lentil sambar.", 500),
        _item("Coconut Chutney", "Sides", "Fresh coconut and green chilli chutney.", 150),
        _item("Mysore Pak", "Desserts", "Ghee-rich gram flour sweet.", 350),
        _item("Filter Coffee", "Beverages", "Strong decoction with frothy milk.", 250),
    ),
    "hyderabadi": (
        _item("Chicken 65", "Starters", "Spicy fried chicken with curry leaves.", 850),
        _item("Apollo Fish", "Starters", "Crispy fish tossed in chilli and yoghurt.", 1000),
        _item("Hyderabadi Chicken Biryani", "Main Course", "Dum-cooked basmati with saffron and chicken.", 1350),
        _item("Mutton Biryani", "Main Course", "Fragrant dum biryani with tender mutton.", 1650),
        _item("Mirchi Ka Salan", "Sides", "Peanut and sesame chilli curry.", 400),
        _item("Raita", "Sides", "Cooling yoghurt with cucumber and mint.", 250),
        _item("Double Ka Meetha", "Desserts", "Fried bread pudding in saffron milk.", 450),
        _item("Irani Chai", "Beverages", "Sweet milky tea, Hyderabadi style.", 250),
    ),
    "punjabi": (
        _item("Amritsari Fish", "Starters", "Crisp gram-flour fried river fish.", 950),
        _item("Paneer Pakora", "Starters", "Batter-fried cottage cheese fritters.", 600),
        _item("Sarson Ka Saag", "Main Course", "Mustard greens slow-cooked with spices.", 750),
        _item("Chole Bhature", "Main Course", "Spicy chickpeas with puffed bread.", 700),
        _item("Kadhi Pakora", "Main Course", "Yoghurt curry with gram-flour dumplings.", 650),
        _item("Makki Roti", "Sides", "Griddled cornmeal flatbread.", 300),
        _item("Boondi Raita", "Sides", "Yoghurt with spiced gram-flour pearls.", 250),
        _item("Pinni", "Desserts", "Ghee and jaggery sweet with nuts.", 400),
        _item("Sweet Lassi", "Beverages", "Thick sweetened yoghurt drink.", 300),
    ),
    "bengali": (
        _item("Fish Fry", "Starters", "Crumb-fried fish cutlet with mustard.", 850),
        _item("Beguni", "Starters", "Crisp battered aubergine fritters.", 450),
        _item("Shorshe Ilish", "Main Course", "Hilsa in a pungent mustard gravy.", 1550),
        _item("Kosha Mangsho", "Main Course", "Slow-cooked spicy mutton curry.", 1500),
        _item("Cholar Dal", "Sides", "Bengal gram dal with coconut.", 400),
        _item("Basanti Pulao", "Sides", "Sweet saffron rice with raisins.", 500),
        _item("Mishti Doi", "Desserts", "Caramelised sweetened yoghurt.", 350),
        _item("Aam Panna", "Beverages", "Tangy raw-mango cooler.", 250),
    ),
    "chinese": (
        _item("Veg Spring Rolls", "Starters", "Crisp rolls with julienned vegetables.", 500),
        _item("Chicken Momos", "Starters", "Steamed dumplings with chilli dip.", 650),
        _item("Chicken Manchurian", "Main Course", "Fried chicken in a tangy soy gravy.", 1050),
        _item("Schezwan Fried Rice", "Main Course", "Fiery wok rice with vegetables.", 900),
        _item("Hakka Noodles", "Main Course", "Stir-fried noodles with vegetables.", 850),
        _item("Crispy Chilli Potato", "Sides", "Sweet-hot sticky potato batons.", 550),
        _item("Date Pancake", "Desserts", "Crisp pancake filled with sticky dates.", 450),
        _item("Green Tea", "Beverages", "Light jasmine green tea.", 250),
    ),
    "thai": (
        _item("Thai Spring Rolls", "Starters", "Glass-noodle rolls with sweet chilli.", 550),
        _item("Tom Yum Soup", "Starters", "Hot and sour lemongrass broth.", 600),
        _item("Pad Thai", "Main Course", "Rice noodles with tamarind and peanuts.", 950),
        _item("Green Thai Curry", "Main Course", "Coconut curry with basil and vegetables.", 1150),
        _item("Thai Basil Fried Rice", "Main Course", "Fragrant rice with holy basil.", 900),
        _item("Som Tam Salad", "Sides", "Green papaya salad with lime.", 500),
        _item("Mango Sticky Rice", "Desserts", "Sweet coconut rice with mango.", 550),
        _item("Thai Iced Tea", "Beverages", "Sweet spiced iced tea with milk.", 350),
    ),
    "japanese": (
        _item("Edamame", "Starters", "Steamed soy beans with sea salt.", 450),
        _item("Vegetable Tempura", "Starters", "Lightly battered crisp vegetables.", 650),
        _item("California Roll", "Main Course", "Crab, avocado and cucumber sushi roll.", 950),
        _item("Salmon Nigiri", "Main Course", "Fresh salmon over seasoned rice.", 1100),
        _item("Chicken Teriyaki Bowl", "Main Course", "Glazed chicken over steamed rice.", 1000),
        _item("Miso Soup", "Sides", "Soybean broth with tofu and seaweed.", 350),
        _item("Mochi Ice Cream", "Desserts", "Chewy rice cake with ice cream.", 500),
        _item("Matcha Latte", "Beverages", "Stone-ground green tea with milk.", 400),
    ),
    "korean": (
        _item("Kimchi Pancake", "Starters", "Crisp savoury pancake with kimchi.", 600),
        _item("Tteokbokki", "Starters", "Chewy rice cakes in spicy gochujang.", 700),
        _item("Korean Fried Chicken", "Main Course", "Double-fried chicken in sticky glaze.", 1100),
        _item("Bibimbap", "Main Course", "Rice bowl with vegetables and egg.", 950),
        _item("Japchae", "Main Course", "Glass noodles with vegetables.", 900),
        _item("Kimchi", "Sides", "Fermented spiced napa cabbage.", 300),
        _item("Hotteok", "Desserts", "Sweet pancake with brown-sugar filling.", 450),
        _item("Iced Yuzu Tea", "Beverages", "Citrus yuzu with honey over ice.", 350),
    ),
    "vietnamese": (
        _item("Summer Rolls", "Starters", "Rice-paper rolls with herbs and dip.", 550),
        _item("Vietnamese Pancake", "Starters", "Crisp turmeric crepe with vegetables.", 600),
        _item("Chicken Pho", "Main Course", "Aromatic noodle soup with chicken.", 900),
        _item("Beef Pho", "Main Course", "Slow-simmered beef noodle soup.", 1000),
        _item("Lemongrass Rice Bowl", "Main Course", "Fragrant rice with lemongrass tofu.", 950),
        _item("Banh Mi", "Sides", "Crusty baguette with pickled vegetables.", 550),
        _item("Che Ba Mau", "Desserts", "Three-colour bean dessert.", 450),
        _item("Vietnamese Iced Coffee", "Beverages", "Strong coffee with condensed milk.", 350),
    ),
    "italian": (
        _item("Tomato Bruschetta", "Starters", "Toasted sourdough with marinated tomatoes.", 700),
        _item("Arancini", "Starters", "Crisp risotto balls with cheese.", 650),
        _item("Spaghetti Bolognese", "Main Course", "Slow-cooked meat ragu over spaghetti.", 1150),
        _item("Lasagna", "Main Course", "Layered pasta with bechamel and ragu.", 1250),
        _item("Mushroom Risotto", "Main Course", "Creamy arborio rice with mushrooms.", 1200),
        _item("Garlic Bread", "Sides", "Baked baguette with garlic butter.", 500),
        _item("Panna Cotta", "Desserts", "Silky vanilla cream with berries.", 550),
        _item("Sparkling Lemonade", "Beverages", "Fizzy lemonade with mint.", 350),
    ),
    "american": (
        _item("Buffalo Wings", "Starters", "Sticky hot wings with blue-cheese dip.", 850),
        _item("Mozzarella Sticks", "Starters", "Fried cheese sticks with marinara.", 650),
        _item("BBQ Bacon Burger", "Main Course", "Smoky patty with bacon and cheddar.", 1350),
        _item("Mac & Cheese", "Main Course", "Creamy baked macaroni with cheese.", 950),
        _item("Grilled Chicken Steak", "Main Course", "Herb-grilled chicken with pepper sauce.", 1400),
        _item("Onion Rings", "Sides", "Golden beer-battered onion rings.", 550),
        _item("Brownie Sundae", "Desserts", "Warm brownie with ice cream.", 600),
        _item("Chocolate Milkshake", "Beverages", "Thick shake with vanilla ice cream.", 500),
    ),
    "mexican": (
        _item("Nachos", "Starters", "Tortilla chips with cheese and salsa.", 650),
        _item("Quesadilla", "Starters", "Grilled tortilla with melted cheese.", 700),
        _item("Chicken Tacos", "Main Course", "Soft tacos with spiced chicken.", 900),
        _item("Burrito Bowl", "Main Course", "Rice, beans, salsa and guacamole.", 1000),
        _item("Enchiladas", "Main Course", "Rolled tortillas in a chilli sauce.", 1050),
        _item("Guacamole & Chips", "Sides", "Fresh avocado dip with lime.", 500),
        _item("Churros", "Desserts", "Cinnamon sugar sticks with chocolate.", 550),
        _item("Horchata", "Beverages", "Sweet rice drink with cinnamon.", 400),
    ),
    "mediterranean": (
        _item("Falafel", "Starters", "Crisp chickpea fritters with tahini.", 550),
        _item("Halloumi Skewers", "Starters", "Grilled cheese with herbs and lemon.", 700),
        _item("Chicken Souvlaki", "Main Course", "Marinated chicken skewers with pita.", 1000),
        _item("Lamb Gyro", "Main Course", "Spiced lamb wrap with tzatziki.", 1100),
        _item("Mezze Platter", "Main Course", "Hummus, baba ghanoush and salads.", 950),
        _item("Hummus", "Sides", "Creamy chickpea dip with olive oil.", 400),
        _item("Baklava", "Desserts", "Layered filo with nuts and honey.", 550),
        _item("Mint Lemonade", "Beverages", "Fresh lemonade with mint.", 350),
    ),
    "middle_eastern": (
        _item("Chicken Shawarma", "Starters", "Spit-roasted chicken with garlic sauce.", 650),
        _item("Kibbeh", "Starters", "Bulghur croquettes with spiced filling.", 600),
        _item("Lamb Mandi", "Main Course", "Smoky slow-roasted lamb with rice.", 1400),
        _item("Chicken Kabsa", "Main Course", "Spiced rice with roasted chicken.", 1200),
        _item("Falafel Wrap", "Main Course", "Falafel, pickles and tahini in pita.", 800),
        _item("Tabbouleh", "Sides", "Parsley, bulghur and lemon salad.", 450),
        _item("Kunafa", "Desserts", "Crisp pastry with cheese and syrup.", 600),
        _item("Ayran", "Beverages", "Chilled salted yoghurt drink.", 300),
    ),
    "healthy_vegan": (
        _item("Edamame & Quinoa Salad", "Starters", "Protein-rich salad with lime dressing.", 550),
        _item("Stuffed Bell Peppers", "Starters", "Baked peppers with herbed rice.", 600),
        _item("Tofu Buddha Bowl", "Main Course", "Tofu, grains and greens with miso.", 850),
        _item("Lentil Curry", "Main Course", "Hearty lentil stew with coconut.", 750),
        _item("Jackfruit Tacos", "Main Course", "Pulled jackfruit in soft tacos.", 800),
        _item("Quinoa Tabouli", "Sides", "Quinoa, parsley and lemon salad.", 500),
        _item("Vegan Chocolate Mousse", "Desserts", "Avocado-cacao mousse.", 500),
        _item("Cold-Pressed Juice", "Beverages", "Seasonal fruit and vegetable juice.", 400),
    ),
    "seafood": (
        _item("Garlic Butter Prawns", "Starters", "Pan-seared prawns in garlic butter.", 1350),
        _item("Crispy Calamari", "Starters", "Fried squid rings with aioli.", 900),
        _item("Fish & Chips", "Main Course", "Battered fish with fries and tartar.", 1200),
        _item("Grilled Salmon", "Main Course", "Salmon fillet with lemon butter.", 1500),
        _item("Seafood Paella", "Main Course", "Saffron rice with prawns and mussels.", 1600),
        _item("Garlic Bread", "Sides", "Toasted bread with garlic butter.", 500),
        _item("Lemon Cheesecake", "Desserts", "Baked cheesecake with citrus.", 650),
        _item("Iced Lemon Tea", "Beverages", "Chilled tea with lemon.", 350),
    ),
    "bakery_dessert": (
        _item("Mini Quiche", "Starters", "Buttery pastry with savoury custard.", 500),
        _item("Veg Puff", "Starters", "Flaky puff with spiced vegetables.", 350),
        _item("Pasta Bake", "Main Course", "Macaroni baked in cheese sauce.", 900),
        _item("Red Velvet Cupcake", "Desserts", "Cocoa sponge with cream cheese.", 450),
        _item("Chocolate Éclair", "Desserts", "Choux pastry with chocolate cream.", 400),
        _item("New York Cheesecake", "Desserts", "Baked vanilla cheesecake.", 650),
        _item("Cinnamon Roll", "Desserts", "Soft roll with cinnamon sugar.", 400),
        _item("Iced Latte", "Beverages", "Espresso over milk and ice.", 350),
    ),
    "french": (
        _item("French Onion Soup", "Starters", "Caramelised onion broth with cheese toast.", 600),
        _item("Quiche Lorraine", "Starters", "Savory tart with bacon and cream.", 650),
        _item("Coq au Vin", "Main Course", "Chicken braised in red wine.", 1400),
        _item("Ratatouille", "Main Course", "Slow-cooked Provencal vegetables.", 900),
        _item("Eggs Benedict", "Main Course", "Poached eggs with hollandaise.", 800),
        _item("Croissant", "Sides", "Flaky all-butter croissant.", 350),
        _item("Crème Brûlée", "Desserts", "Vanilla custard with caramel crust.", 600),
        _item("Café au Lait", "Beverages", "Coffee with steamed milk.", 350),
    ),
}

# --------------------------------------------------------------------------
# Generated restaurants: one line each, reusing a cuisine menu template.
# Adding another 25 is just more entries here.
# --------------------------------------------------------------------------
GENERATED = (
    dict(id="rest_tandoor", name="Tandoori Trail", cuisine="North Indian", menu="north_indian",
         description="Clay-oven kebabs, curries and buttery naans."),
    dict(id="rest_madras", name="Madras Coffee House", cuisine="South Indian", menu="south_indian",
         description="Crisp dosas, steaming idlis and filter coffee."),
    dict(id="rest_biryani", name="The Biryani House", cuisine="Hyderabadi", menu="hyderabadi",
         description="Dum biryanis, kebabs and Hyderabadi classics."),
    dict(id="rest_roll", name="Wok & Roll", cuisine="Thai", menu="thai",
         description="Thai curries, noodles and fragrant street food."),
    dict(id="rest_sushi", name="Sushi Sensei", cuisine="Japanese", menu="japanese",
         description="Fresh sushi, ramen and Japanese favourites."),
    dict(id="rest_taco", name="El Taco Loco", cuisine="Mexican", menu="mexican",
         description="Tacos, burritos and bold Mexican flavours."),
    dict(id="rest_med", name="Casa Verde", cuisine="Mediterranean", menu="mediterranean",
         description="Grills, mezze and fresh Mediterranean plates."),
    dict(id="rest_punjab", name="Punjab Grill", cuisine="Punjabi", menu="punjabi",
         description="Hearty Punjabi curries and tandoori breads."),
    dict(id="rest_bengal", name="Bengal Bites", cuisine="Bengali", menu="bengali",
         description="Fish curries, sweets and Kolkata street food."),
    dict(id="rest_vegan", name="The Vegan Table", cuisine="Vegan", menu="healthy_vegan",
         description="Plant-based bowls, curries and cold-pressed juices."),
    dict(id="rest_shawarma", name="Shawarma Street", cuisine="Middle Eastern", menu="middle_eastern",
         description="Wraps, grills and Levantine street eats."),
    dict(id="rest_napoli", name="Napoli Pizzeria", cuisine="Italian", menu="italian",
         description="Wood-fired pizzas, pastas and Italian classics."),
    dict(id="rest_seoul", name="Seoul Kitchen", cuisine="Korean", menu="korean",
         description="Korean fried chicken, bibimbap and kimchi."),
    dict(id="rest_pho", name="Hanoi Pho", cuisine="Vietnamese", menu="vietnamese",
         description="Pho, banh mi and fresh Vietnamese flavours."),
    dict(id="rest_bistro", name="Le Bistro", cuisine="French", menu="french",
         description="Classic French bistro plates and pastries."),
    dict(id="rest_curryleaf", name="Curry Leaf", cuisine="South Indian", menu="south_indian",
         description="Vegetarian South-Indian thalis and tiffins."),
    dict(id="rest_dessertlab", name="The Dessert Lab", cuisine="Desserts", menu="bakery_dessert",
         description="Cakes, bakes and experimental sweet treats."),
)


def _slug(restaurant_id: str) -> str:
    return restaurant_id[len("rest_"):] if restaurant_id.startswith("rest_") else restaurant_id


def build_catalog():
    """Deterministic full catalog: (restaurant, items) with images/categories."""
    catalog = []
    category_cursor = {cat: 0 for cat in CATEGORY_ORDER}
    for index, spec in enumerate(LEGACY + GENERATED):
        image = RESTAURANT_IMAGES[index % len(RESTAURANT_IMAGES)]
        if "items" in spec:
            raw_items = [
                dict(
                    id=it["id"], name=it["name"], category=it["category"],
                    description=it["description"], price_minor=it["price_minor"],
                    is_active=it.get("is_active", True),
                )
                for it in spec["items"]
            ]
        else:
            slug = _slug(spec["id"])
            raw_items = [
                dict(
                    id=f"item_{slug}_{n}", name=t["name"], category=t["category"],
                    description=t["description"], price_minor=t["price_minor"],
                    is_active=t.get("is_active", True),
                )
                for n, t in enumerate(MENUS[spec["menu"]], 1)
            ]
        items = []
        for item in raw_items:
            pool = CATEGORY_IMAGES.get(item["category"], ())
            if pool:
                item["image_url"] = pool[category_cursor.get(item["category"], 0) % len(pool)]
                category_cursor[item["category"]] = category_cursor.get(item["category"], 0) + 1
            else:
                item["image_url"] = ""
            items.append(item)
        catalog.append(dict(
            id=spec["id"], name=spec["name"], cuisine=spec["cuisine"],
            description=spec["description"], image_url=image, items=tuple(items),
        ))
    return tuple(catalog)


CATALOG = build_catalog()


def expected_counts() -> tuple[int, int]:
    """(restaurants, menu items) the seed guarantees after any run."""
    return len(CATALOG), sum(len(r["items"]) for r in CATALOG)


async def upsert_user(session, *, id: str, email: str, role: str, name: str):
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user is None:
        session.add(User(id=id, email=email, password_hash=hash_password(PASSWORD), role=role, name=name))
        print(f"user {email} created")
    else:
        print(f"user {email} already present")


async def upsert_driver(session, *, id: str, name: str):
    driver = await session.get(Driver, id)
    if driver is None:
        session.add(Driver(id=id, name=name, is_active=True))
    else:
        driver.name = name
        driver.is_active = True


async def upsert_restaurant(session, *, id, name, description, cuisine, image_url):
    rest = await session.get(Restaurant, id)
    if rest is None:
        session.add(Restaurant(id=id, name=name, description=description, cuisine=cuisine, image_url=image_url))
    else:
        rest.name = name
        rest.description = description
        rest.cuisine = cuisine
        rest.image_url = image_url


async def upsert_item(session, *, id, restaurant_id, name, description, category,
                      image_url, price_minor, is_active=True):
    item = await session.get(MenuItem, id)
    if item is None:
        session.add(MenuItem(id=id, restaurant_id=restaurant_id, name=name,
                             description=description, category=category, image_url=image_url,
                             price_minor=price_minor, currency="INR", is_active=is_active))
    else:
        item.restaurant_id = restaurant_id
        item.name = name
        item.description = description
        item.category = category
        item.image_url = image_url
        item.price_minor = price_minor
        item.currency = "INR"
        item.is_active = is_active


async def main() -> None:
    settings = get_settings()
    init_db(settings.DATABASE_URL)
    factory = session_factory()
    async with factory() as session:
        async with session.begin():
            for user in USERS:
                await upsert_user(session, **user)
            for driver in DRIVERS:
                await upsert_driver(session, **driver)
            for restaurant in CATALOG:
                await upsert_restaurant(
                    session,
                    id=restaurant["id"], name=restaurant["name"],
                    description=restaurant["description"], cuisine=restaurant["cuisine"],
                    image_url=restaurant["image_url"],
                )
                for item in restaurant["items"]:
                    await upsert_item(session, restaurant_id=restaurant["id"], **item)
    restaurants, items = expected_counts()
    print(f"seed complete: {restaurants} restaurants, {items} menu items")


if __name__ == "__main__":
    asyncio.run(main())
