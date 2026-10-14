// Riverpod providers: session, API client, cart, polling.
import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../models/models.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

/// Shared restaurant search text. The navbar and the home search bar both
/// write here; the list screen listens and re-queries the backend.
final restaurantQueryProvider = StateProvider<String>((ref) => '');

class Session extends StateNotifier<UserSummary?> {
  final ApiClient _api;
  Session(this._api) : super(null);

  void signIn(UserSummary user) => state = user;

  /// Clears the persisted token as well as the in-memory session so a stale
  /// credential can never be reused after logout.
  Future<void> signOut() async {
    state = null;
    try {
      await _api.signOut();
    } catch (_) {
      // Storage teardown is best-effort; the in-memory session is already gone.
    }
  }

  bool get isAdmin => state?.role == 'admin';
}

final sessionProvider =
    StateNotifierProvider<Session, UserSummary?>(
        (ref) => Session(ref.watch(apiClientProvider)));

class CartState extends StateNotifier<Cart> {
  CartState() : super(Cart());

  void add(MenuItem item, int quantity) {
    state.add(item, quantity);
    state = _copy(state);
  }

  void remove(String id) {
    state.remove(id);
    state = _copy(state);
  }

  void changeQuantity(String id, int delta) {
    state.changeQuantity(id, delta);
    state = _copy(state);
  }

  void clear() => state = Cart();

  static Cart _copy(Cart cart) {
    final next = Cart()
      ..restaurantId = cart.restaurantId;
    next.lines.addAll(cart.lines);
    return next;
  }
}

final cartProvider =
    StateNotifierProvider<CartState, Cart>((ref) => CartState());

/// Polls order details ~every 2s while visible. Stops on terminal status,
/// dispose, or sign-out; backs off after failures.
class OrderPoller extends StateNotifier<AsyncValue<Map<String, dynamic>>> {
  final ApiClient _api;
  Timer? _timer;
  int _failures = 0;
  bool _disposed = false;

  OrderPoller(this._api) : super(const AsyncValue.loading());

  void start(String orderId) {
    stop();
    _disposed = false;
    _fetch(orderId);
    _timer = Timer.periodic(const Duration(seconds: 2), (_) {
      if (_disposed) return;
      if (_failures > 0) {
        // Back off after failures: skip ticks proportionally.
        if (DateTime.now().millisecondsSinceEpoch % (_failures + 1) != 0) {
          return;
        }
      }
      _fetch(orderId);
    });
  }

  Future<void> _fetch(String orderId) async {
    try {
      final body = await _api.getJson('/api/v1/orders/$orderId');
      if (_disposed) return;
      _failures = 0;
      state = AsyncValue.data(body);
      final status = (body['status'] ?? '') as String;
      if (isTerminalStatus(status)) stop();
    } on ApiException catch (err, stack) {
      if (_disposed) return;
      _failures++;
      if (err.isAuthExpired) {
        stop();
        state = AsyncValue.error(err, stack);
        return;
      }
      if (state is! AsyncData) state = AsyncValue.error(err, stack);
    }
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
  }

  @override
  void dispose() {
    _disposed = true;
    stop();
    super.dispose();
  }
}

final orderPollerProvider = StateNotifierProvider<OrderPoller,
    AsyncValue<Map<String, dynamic>>>(
  (ref) => OrderPoller(ref.watch(apiClientProvider)),
);

/// Persists the pending checkout key + request until the outcome is known,
/// so a timeout can retry with the SAME key after a restart.
class PendingCheckout {
  static const storageKey = 'quickbite_pending_checkout';

  static Future<void> save(
      String idempotencyKey, Map<String, dynamic> body) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
        storageKey, jsonEncode({'key': idempotencyKey, 'body': body}));
  }

  static Future<PendingCheckoutData?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(storageKey);
    if (raw == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      return PendingCheckoutData(
          key: map['key'] as String,
          body: Map<String, dynamic>.from(map['body'] as Map));
    } catch (_) {
      return null;
    }
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(storageKey);
  }
}

class PendingCheckoutData {
  final String key;
  final Map<String, dynamic> body;

  const PendingCheckoutData({required this.key, required this.body});
}
