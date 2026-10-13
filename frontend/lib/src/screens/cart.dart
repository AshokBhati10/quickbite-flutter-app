// Cart + checkout: quantities, removal, subtotal, address validation,
// single-restaurant rule, UUID idempotency key, safe timeout retry.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../widgets/app_scaffold.dart';

class CartScreen extends ConsumerStatefulWidget {
  const CartScreen({super.key});

  @override
  ConsumerState<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends ConsumerState<CartScreen> {
  final _address = TextEditingController();
  bool _active = false;
  String? _error;
  bool _timedOut = false;
  String? _pendingKey;
  Map<String, dynamic>? _pendingBody;

  String? _validate(Cart cart) {
    if (cart.isEmpty) return 'Add items to your cart before checkout.';
    if (_address.text.trim().length < 8) {
      return 'Enter a delivery address of at least 8 characters.';
    }
    if (cart.distinctCount > 20) return 'At most 20 distinct items per order.';
    return null;
  }

  Future<void> _checkout() async {
    final cart = ref.read(cartProvider);
    final problem = _validate(cart);
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    final key = _pendingKey ?? const Uuid().v4();
    final body = _pendingBody ?? cart.toCheckoutJson(_address.text.trim());
    setState(() {
      _active = true;
      _error = null;
      _timedOut = false;
      _pendingKey = key;
      _pendingBody = body;
    });
    await PendingCheckout.save(key, body);
    CheckoutResult result;
    try {
      result = await ref
          .read(apiClientProvider)
          .checkout(body: body, idempotencyKey: key);
    } on ApiException catch (err) {
      if (!mounted) return;
      if (err.isAuthExpired) {
        ref.read(sessionProvider.notifier).signOut();
        return;
      }
      setState(() {
        _error = err.message;
        _active = false;
      });
      return;
    }
    if (!mounted) return;
    if (result.timedOut) {
      // Outcome unknown: keep the SAME key and offer a safe retry.
      setState(() {
        _timedOut = true;
        _active = false;
      });
      return;
    }
    await PendingCheckout.clear();
    ref.read(cartProvider.notifier).clear();
    setState(() {
      _active = false;
      _pendingKey = null;
      _pendingBody = null;
    });
    if (!mounted) return;
    Navigator.of(context).pushReplacementNamed('/ack', arguments: {
      'order_id': result.orderId,
      'status': result.status,
      'total': result.totalMinor,
      'currency': result.currency,
    });
  }

  @override
  Widget build(BuildContext context) {
    final cart = ref.watch(cartProvider);
    final lines = cart.lines.values.toList();
    return ResponsiveScaffold(
      title: 'Cart',
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (lines.isEmpty)
            const EmptyView(message: 'Your cart is empty.'),
          for (final line in lines)
            ListTile(
              title: Text(line.item.name),
              subtitle: Text(
                  '${formatMinor(line.item.priceMinor, line.item.currency)} x ${line.quantity}'),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    icon: const Icon(Icons.remove),
                    tooltip: 'Remove one',
                    onPressed: () => ref
                        .read(cartProvider.notifier)
                        .changeQuantity(line.item.id, -1),
                  ),
                  IconButton(
                    icon: const Icon(Icons.delete),
                    tooltip: 'Remove ${line.item.name}',
                    onPressed: () => ref
                        .read(cartProvider.notifier)
                        .remove(line.item.id),
                  ),
                ],
              ),
            ),
          if (lines.isNotEmpty)
            Text('Subtotal: ${formatMinor(cart.subtotal, 'INR')}',
                style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          TextField(
            controller: _address,
            decoration: const InputDecoration(
                labelText: 'Delivery address',
                hintText: '12 Lake Road, Bengaluru'),
            maxLines: 2,
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Text(_error!, style: const TextStyle(color: Colors.red)),
          if (_timedOut)
            const Text(
                'The request timed out. The order may already exist: retrying uses the same key and never creates a duplicate.'),
          const SizedBox(height: 8),
          ElevatedButton(
            onPressed: _active ? null : _checkout,
            child: Text(_active
                ? 'Placing order…'
                : _timedOut
                    ? 'Retry with same key'
                    : 'Place order'),
          ),
        ],
      ),
    );
  }
}

class OrderAckScreen extends StatelessWidget {
  final Map<String, dynamic> accepted;
  const OrderAckScreen({super.key, required this.accepted});

  @override
  Widget build(BuildContext context) {
    return ResponsiveScaffold(
      title: 'Order accepted',
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Order ID: ${accepted['order_id']}'),
          Text('Status: ${accepted['status']}'),
          Text(
              'Accepted total: ${formatMinor((accepted['total'] ?? 0) as int, (accepted['currency'] ?? 'INR') as String)}'),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pushReplacementNamed(
                '/order',
                arguments: accepted['order_id']),
            child: const Text('Track order'),
          ),
        ],
      ),
    );
  }
}
