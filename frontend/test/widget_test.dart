// Widget tests: navbar (auth + public states), profile menu, cart badge,
// My Orders, sign-in, cart validation, restaurant cards/pagination, menu.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:quickbite/src/api/api_client.dart';
import 'package:quickbite/src/models/models.dart';
import 'package:quickbite/src/providers/providers.dart';
import 'package:quickbite/src/screens/cart.dart';
import 'package:quickbite/src/screens/history_admin.dart';
import 'package:quickbite/src/screens/order_details.dart';
import 'package:quickbite/src/screens/restaurants.dart';
import 'package:quickbite/src/screens/sign_in.dart';
import 'package:quickbite/src/widgets/app_navbar.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _customer = UserSummary(
    id: 'user_customer',
    email: 'customer@quickbite.test',
    role: 'customer',
    name: 'Demo Customer');

Map<String, dynamic> _restaurantJson(int i) => {
      'id': 'rest_$i',
      'name': 'Restaurant $i',
      'description': 'Tasty food from kitchen $i.',
      'cuisine': 'Cuisine ${i % 5}',
      'image_url': '',
      'is_active': true,
    };

Map<String, dynamic> _itemJson(String id, String name, String category,
        String description, int price, {bool active = true}) =>
    {
      'id': id,
      'restaurant_id': 'rest_x',
      'name': name,
      'description': description,
      'category': category,
      'image_url': '',
      'price_minor': price,
      'currency': 'INR',
      'is_active': active,
    };

Map<String, dynamic> _orderJson(
        {String id = 'order_1',
        String restaurant = 'Spice Route',
        String status = 'PENDING',
        int total = 2900}) =>
    {
      'id': id,
      'status': status,
      'total_minor': total,
      'currency': 'INR',
      'version': 1,
      'restaurant_name': restaurant,
      'created_at': '2026-10-13T10:00:00+00:00',
      'items': [
        {
          'menu_item_id': 'item_biryani',
          'name': 'Butter Chicken',
          'unit_price_minor': 1450,
          'quantity': 2,
        }
      ],
    };

// In-memory API: serves paginated restaurants, menus, order history and the
// authenticated profile without any network access.
class _CatalogApi extends ApiClient {
  final List<Map<String, dynamic>> restaurants;
  final Map<String, List<Map<String, dynamic>>> menus;
  final List<Map<String, dynamic>> orders;

  _CatalogApi(
      {this.restaurants = const [], this.menus = const {}, this.orders = const []});

  @override
  Future<Map<String, dynamic>> getJson(String path,
      {Map<String, String>? query}) async {
    if (path == '/api/v1/me') {
      return {
        'id': _customer.id,
        'email': _customer.email,
        'role': _customer.role,
        'name': _customer.name,
      };
    }
    if (path == '/api/v1/restaurants/cuisines') {
      return {
        'items': ['Italian', 'South Indian']
      };
    }
    if (path == '/api/v1/restaurants') {
      final page = int.tryParse(query?['page'] ?? '1') ?? 1;
      final size = int.tryParse(query?['page_size'] ?? '5') ?? 5;
      final q = (query?['q'] ?? '').toLowerCase();
      final cuisine = (query?['cuisine'] ?? '').toLowerCase();
      var list = restaurants;
      if (q.isNotEmpty) {
        list = list
            .where((r) =>
                (r['name'] as String).toLowerCase().contains(q) ||
                (r['cuisine'] as String).toLowerCase().contains(q))
            .toList();
      }
      if (cuisine.isNotEmpty) {
        list = list
            .where((r) => (r['cuisine'] as String).toLowerCase() == cuisine)
            .toList();
      }
      final start = (page - 1) * size;
      final slice = start >= list.length
          ? <Map<String, dynamic>>[]
          : list.sublist(start, (start + size).clamp(0, list.length));
      return {
        'items': slice,
        'page': page,
        'page_size': size,
        'total': list.length,
      };
    }
    final menuMatch =
        RegExp(r'^/api/v1/restaurants/([^/]+)/menu$').firstMatch(path);
    if (menuMatch != null) {
      final items = menus[menuMatch.group(1)!] ?? const [];
      return {'items': items, 'page': 1, 'page_size': 100, 'total': items.length};
    }
    if (path == '/api/v1/orders') {
      return {
        'items': orders,
        'page': 1,
        'page_size': 20,
        'total': orders.length,
      };
    }
    if (path.endsWith('/history')) return {'items': []};
    if (path.endsWith('/notifications')) {
      return {'items': [], 'page': 1, 'page_size': 50, 'total': 0};
    }
    if (path.startsWith('/api/v1/orders/')) {
      return orders.isNotEmpty
          ? orders.first
          : {
              'id': 'order_1',
              'status': 'PENDING',
              'total_minor': 2900,
              'currency': 'INR',
              'version': 1,
            };
    }
    return {};
  }
}

ProviderContainer _container(_CatalogApi api, {UserSummary? session}) {
  final container =
      ProviderContainer(overrides: [apiClientProvider.overrideWithValue(api)]);
  if (session != null) {
    container.read(sessionProvider.notifier).signIn(session);
  }
  return container;
}

Widget _app(ProviderContainer container, Widget home) =>
    UncontrolledProviderScope(
        container: container, child: MaterialApp(home: home));

void main() {
  testWidgets('login page shows only the logo and form, no navbar',
      (tester) async {
    await tester.pumpWidget(
        const ProviderScope(child: MaterialApp(home: SignInScreen())));
    await tester.pump();
    expect(find.text('QuickBite'), findsOneWidget);
    expect(find.text('QuickBite sign in'), findsOneWidget);
    expect(find.byKey(const Key('email')), findsOneWidget);
    expect(find.byKey(const Key('password')), findsOneWidget);
    expect(find.byKey(const Key('signIn')), findsOneWidget);
    // No navigation chrome is exposed to a signed-out user.
    expect(find.byType(AppNavBar), findsNothing);
    expect(find.byTooltip('Account'), findsNothing);
    expect(find.byTooltip('Open menu'), findsNothing);
  });

  testWidgets('authenticated navbar shows the real name and profile actions',
      (tester) async {
    tester.view.physicalSize = const Size(1400, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    final container = _container(_CatalogApi(), session: _customer);
    addTearDown(container.dispose);
    await tester.pumpWidget(_app(
        container,
        const Scaffold(
            appBar: AppNavBar(), body: SizedBox(), drawer: NavDrawer())));
    await tester.pump();

    expect(find.text('Demo Customer'), findsOneWidget);
    await tester.tap(find.byTooltip('Account menu'));
    await tester.pumpAndSettle();
    expect(find.text('customer@quickbite.test'), findsOneWidget);
    expect(find.text('My Orders'), findsWidgets);
    expect(find.text('Profile Details'), findsOneWidget);
    expect(find.text('Logout'), findsOneWidget);
  });

  testWidgets('navbar renders without overflow across widths', (tester) async {
    for (final width in [320.0, 360.0, 768.0, 1024.0, 1440.0]) {
      tester.view.physicalSize = Size(width, 800);
      tester.view.devicePixelRatio = 1.0;
      final container = _container(_CatalogApi(), session: _customer);
      await tester.pumpWidget(_app(
          container,
          const Scaffold(
              appBar: AppNavBar(), body: SizedBox(), drawer: NavDrawer())));
      await tester.pump();
      expect(tester.takeException(), isNull, reason: 'width $width');
      container.dispose();
    }
    tester.view.resetPhysicalSize();
  });

  testWidgets('navbar cart badge reflects the real cart state', (tester) async {
    final api = _CatalogApi();
    final container = _container(api, session: _customer);
    addTearDown(container.dispose);
    container.read(cartProvider.notifier).add(
        const MenuItem(
            id: 'm1',
            restaurantId: 'rest_x',
            name: 'Paneer Tikka',
            priceMinor: 850,
            currency: 'INR',
            isActive: true),
        3);

    await tester
        .pumpWidget(_app(container, const Scaffold(appBar: AppNavBar(), body: SizedBox())));
    await tester.pump();
    expect(find.text('3'), findsOneWidget);
  });

  testWidgets('cart badge counts up 0 -> 1 -> 2 as menu items are added',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = const Size(1000, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    final api = _CatalogApi(menus: {
      'rest_x': [
        _itemJson('m1', 'Paneer Tikka', 'Starters', 'Smoky cottage cheese.', 850),
        _itemJson('m2', 'Garlic Naan', 'Sides', 'Tandoor-baked bread.', 150),
      ]
    });
    final container = _container(api, session: _customer);
    addTearDown(container.dispose);
    await tester.pumpWidget(_app(
        container,
        const MenuScreen(
          restaurant: Restaurant(
              id: 'rest_x',
              name: 'Tandoori Trail',
              description: 'Clay-oven kebabs.',
              cuisine: 'North Indian',
              isActive: true),
        )));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    Text badge() =>
        tester.widget<Text>(find.byKey(const Key('cartCount')));
    expect(badge().data, '0');

    await tester.tap(find.byTooltip('Add Paneer Tikka to cart'));
    await tester.pump();
    expect(badge().data, '1');

    await tester.tap(find.byTooltip('Add Garlic Naan to cart'));
    await tester.pump();
    expect(badge().data, '2');
  });

  testWidgets('cart validates empty checkout', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(
        const ProviderScope(child: MaterialApp(home: CartScreen())));
    await tester.tap(find.text('Place order'));
    await tester.pump();
    expect(find.text('Add items to your cart before checkout.'), findsOneWidget);
  });

  testWidgets('cart renders phone and desktop sizes without overflow',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    for (final size in [
      const Size(360, 740),
      const Size(1280, 800),
    ]) {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1.0;
      await tester.pumpWidget(ProviderScope(
          child: MaterialApp(
              home: CartScreen(key: Key('cart-${size.width}')))));
      await tester.pump();
      expect(tester.takeException(), isNull);
    }
    tester.view.resetPhysicalSize();
  });

  testWidgets('large text scale does not overflow cart', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const ProviderScope(
        child: MediaQuery(
            data: MediaQueryData(textScaler: TextScaler.linear(2.0)),
            child: MaterialApp(home: CartScreen()))));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('restaurant list paginates five per page', (tester) async {
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = const Size(1400, 1400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    final api = _CatalogApi(
        restaurants: [for (var i = 0; i < 25; i++) _restaurantJson(i)]);
    final container = _container(api, session: _customer);
    addTearDown(container.dispose);
    await tester.pumpWidget(_app(container, const RestaurantListScreen()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Discover Restaurants'), findsOneWidget);
    expect(find.byType(Card), findsNWidgets(5));
    expect(find.text('Page 1 of 5'), findsOneWidget);
    expect(find.text('Restaurant 0'), findsOneWidget);
    expect(find.text('Restaurant 5'), findsNothing);

    await tester.tap(find.text('Next'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Page 2 of 5'), findsOneWidget);
    expect(find.text('Restaurant 5'), findsOneWidget);
    expect(find.text('Restaurant 0'), findsNothing);

    await tester.tap(find.text('Previous'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Page 1 of 5'), findsOneWidget);
    expect(find.text('Restaurant 0'), findsOneWidget);
  });

  testWidgets('hero search filters the list by name or cuisine',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = const Size(800, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    final api = _CatalogApi(restaurants: [
      {
        'id': 'rest_pasta',
        'name': 'Pasta Palace',
        'description': 'Fresh pasta.',
        'cuisine': 'Italian',
        'image_url': '',
        'is_active': true,
      },
      {
        'id': 'rest_burger',
        'name': 'Burger Barn',
        'description': 'Flame-grilled.',
        'cuisine': 'American',
        'image_url': '',
        'is_active': true,
      },
    ]);
    final container = _container(api, session: _customer);
    addTearDown(container.dispose);
    await tester.pumpWidget(_app(container, const RestaurantListScreen()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Pasta Palace'), findsOneWidget);
    expect(find.text('Burger Barn'), findsOneWidget);

    final field = find.descendant(
        of: find.byKey(const Key('heroSearch')),
        matching: find.byType(TextField));
    await tester.enterText(field, 'italian');
    await tester.pump(const Duration(milliseconds: 450));
    await tester.pump();
    expect(find.text('Pasta Palace'), findsOneWidget);
    expect(find.text('Burger Barn'), findsNothing);
  });

  testWidgets('menu shows categories, descriptions, price and sold-out state',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = const Size(900, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    final api = _CatalogApi(menus: {
      'rest_x': [
        _itemJson('m1', 'Paneer Tikka', 'Starters',
            'Smoky cottage cheese in a spiced marinade.', 850),
        _itemJson('m2', 'Rogan Josh', 'Main Course',
            'Kashmiri lamb curry with warm spices.', 1550,
            active: false),
      ]
    });
    await tester.pumpWidget(ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(api)],
      child: const MaterialApp(
        home: MenuScreen(
          restaurant: Restaurant(
              id: 'rest_x',
              name: 'Tandoori Trail',
              description: 'Clay-oven kebabs.',
              cuisine: 'North Indian',
              isActive: true),
        ),
      ),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Starters'), findsOneWidget);
    expect(find.text('Main Course'), findsOneWidget);
    expect(find.text('Smoky cottage cheese in a spiced marinade.'),
        findsOneWidget);
    expect(find.text('INR 8.50'), findsOneWidget);
    expect(find.text('Sold out'), findsOneWidget);
    expect(find.byTooltip('Add Paneer Tikka to cart'), findsOneWidget);
    expect(find.byTooltip('Add Rogan Josh to cart'), findsNothing);

    await tester.tap(find.byTooltip('Add Paneer Tikka to cart'));
    await tester.pump();
    expect(find.text('Paneer Tikka added to cart'), findsOneWidget);
  });

  testWidgets('my orders renders real history with items and total',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = const Size(1000, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    final api = _CatalogApi(orders: [
      _orderJson(id: 'order_a', restaurant: 'Spice Route', total: 2900),
      _orderJson(
          id: 'order_b',
          restaurant: 'Napoli Pizzeria',
          status: 'DRIVER_ASSIGNED',
          total: 1150),
    ]);
    final container = _container(api, session: _customer);
    addTearDown(container.dispose);
    await tester.pumpWidget(_app(container, const OrderHistoryScreen()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Spice Route'), findsOneWidget);
    expect(find.text('Napoli Pizzeria'), findsOneWidget);
    expect(find.text('Order order_a'), findsOneWidget);
    expect(find.text('2 × Butter Chicken'), findsNWidgets(2));
    expect(find.text('INR 29.00'), findsOneWidget);
    expect(find.text('PENDING'), findsOneWidget);
    expect(find.text('DRIVER ASSIGNED'), findsOneWidget);
    expect(find.text('View Details'), findsNWidgets(2));
  });

  testWidgets('my orders empty state offers browsing restaurants',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = _CatalogApi(orders: const []);
    final container = _container(api, session: _customer);
    addTearDown(container.dispose);
    await tester.pumpWidget(_app(container, const OrderHistoryScreen()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('No orders yet'), findsOneWidget);
    expect(find.text('Browse Restaurants'), findsOneWidget);
  });

  testWidgets('order tracking "Order More" returns to restaurants',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(_CatalogApi())],
      child: MaterialApp(
        routes: {'/restaurants': (_) => const RestaurantListScreen()},
        home: const OrderDetailsScreen(orderId: 'order_1'),
      ),
    ));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Order More'), findsOneWidget);

    await tester.tap(find.byKey(const Key('orderMore')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.byType(RestaurantListScreen), findsOneWidget);
  });

  testWidgets('discovery and menu render without overflow (phone + desktop)',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = _CatalogApi(
      restaurants: [for (var i = 0; i < 5; i++) _restaurantJson(i)],
      menus: {
        'rest_0': [
          _itemJson('m1', 'Paneer Tikka', 'Starters',
              'Smoky cottage cheese in a spiced marinade.', 850),
        ],
      },
    );

    for (final size in [const Size(360, 740), const Size(1280, 900)]) {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1.0;
      final container = _container(api, session: _customer);
      await tester.pumpWidget(_app(container, const RestaurantListScreen()));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(tester.takeException(), isNull, reason: 'discovery $size');
      container.dispose();
    }

    for (final size in [const Size(360, 740), const Size(1280, 900)]) {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1.0;
      await tester.pumpWidget(ProviderScope(
        overrides: [apiClientProvider.overrideWithValue(api)],
        child: const MaterialApp(
          home: MenuScreen(
            restaurant: Restaurant(
                id: 'rest_0',
                name: 'Kitchen 0',
                description: 'Tasty food from kitchen 0.',
                cuisine: 'North Indian',
                isActive: true),
          ),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(tester.takeException(), isNull, reason: 'menu $size');
    }
    tester.view.resetPhysicalSize();
  });
}
