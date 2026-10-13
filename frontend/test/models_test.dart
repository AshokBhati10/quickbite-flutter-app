// Unit tests: models JSON parsing, cart logic, polling controller,
// pending-checkout persistence.
import 'package:flutter_test/flutter_test.dart';
import 'package:quickbite/src/models/models.dart';
import 'package:quickbite/src/providers/providers.dart';
import 'package:shared_preferences/shared_preferences.dart';

MenuItem _item(String id, String rest, {bool active = true}) => MenuItem(
    id: id,
    restaurantId: rest,
    name: 'Item $id',
    priceMinor: 1250,
    currency: 'INR',
    isActive: active);

void main() {
  test('order summary parses both list and accept shapes', () {
    final fromList = OrderSummary.fromJson({
      'id': 'order_1',
      'status': 'PENDING',
      'total_minor': 2900,
      'currency': 'INR',
      'version': 1,
    });
    expect(fromList.totalMinor, 2900);
    final fromAccept = OrderSummary.fromJson({
      'id': 'order_1',
      'status': 'PENDING',
      'total_amount_minor': 2900,
      'currency': 'INR',
      'version': 1,
    });
    expect(fromAccept.totalMinor, 2900);
  });

  test('cart enforces single restaurant and quantity bounds', () {
    final cart = Cart();
    cart.add(_item('a', 'r1'), 2);
    cart.add(_item('b', 'r2'), 1);
    expect(cart.restaurantId, 'r2');
    expect(cart.distinctCount, 1);
    expect(cart.subtotal, 1250);
    cart.changeQuantity('b', 30);
    expect(cart.lines['b']!.quantity, 20);
    cart.changeQuantity('b', -20);
    expect(cart.isEmpty, true);
  });

  test('failure explanation distinguishes notification failure', () {
    // A notification failure must not read as a payment failure.
    expect(
        failureExplanation('notification_failed', 'PAID'), isEmpty);
    expect(failureExplanation('payment_failed', 'PAYMENT_FAILED'),
        contains('Payment'));
  });

  test('pending checkout persists key and body', () async {
    SharedPreferences.setMockInitialValues({});
    await PendingCheckout.save('key-1', {
      'restaurant_id': 'r1',
      'delivery_address': '12 Lake Road, Bengaluru',
      'items': [
        {'menu_item_id': 'a', 'quantity': 1}
      ],
    });
    final loaded = await PendingCheckout.load();
    expect(loaded!.key, 'key-1');
    expect(
        (loaded.body['items'] as List).first['menu_item_id'], 'a');
    await PendingCheckout.clear();
    expect(await PendingCheckout.load(), isNull);
  });
}
