// QuickBite Flutter app: web, Android, iOS from one project.
// Configure with --dart-define=API_BASE_URL=<reachable api>.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'src/models/models.dart';
import 'src/providers/providers.dart';
import 'src/screens/cart.dart';
import 'src/screens/history_admin.dart';
import 'src/screens/order_details.dart';
import 'src/screens/profile.dart';
import 'src/screens/register.dart';
import 'src/screens/restaurants.dart';
import 'src/screens/sign_in.dart';
import 'src/theme/app_theme.dart';

void main() {
  runApp(const ProviderScope(child: QuickBiteApp()));
}

class QuickBiteApp extends ConsumerWidget {
  const QuickBiteApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    return MaterialApp(
      title: 'QuickBite',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      // Named routes double as web deep links (/order/:id handled via
      // onGenerateRoute arguments; direct URL entry lands on home).
      routes: {
        '/signin': (context) => const SignInScreen(),
        '/register': (context) => const RegisterScreen(),
        '/restaurants': (context) => const RestaurantListScreen(),
        '/history': (context) => const OrderHistoryScreen(),
        '/profile': (context) => const ProfileDetailsScreen(),
        '/cart': (context) => const CartScreen(),
        '/admin': (context) => const AdminOverviewScreen(),
      },
      onGenerateRoute: (settings) {
        switch (settings.name) {
          case '/menu':
            final restaurant = settings.arguments as Restaurant;
            return MaterialPageRoute(
                builder: (_) => MenuScreen(restaurant: restaurant));
          case '/order':
            final orderId = settings.arguments as String;
            return MaterialPageRoute(
                builder: (_) => OrderDetailsScreen(orderId: orderId));
          case '/ack':
            final accepted = settings.arguments as Map<String, dynamic>;
            return MaterialPageRoute(
                builder: (_) => OrderAckScreen(accepted: accepted));
        }
        return null;
      },
      home: session == null
          ? const SignInScreen()
          : const RestaurantListScreen(),
    );
  }
}
