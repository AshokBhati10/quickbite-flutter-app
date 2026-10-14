// Cart + checkout: quantities, removal, subtotal, address validation,
// single-restaurant rule, UUID idempotency key, safe timeout retry.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/app_scaffold.dart';
import '../widgets/media.dart';
import '../widgets/ui.dart';

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
      body: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth > 880;
          if (!wide) {
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
              children: [
                if (lines.isEmpty)
                  const EmptyView(
                      message: 'Your cart is empty.',
                      icon: Icons.shopping_bag_outlined),
                for (final line in lines)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _CartLineCard(line: line),
                  ),
                const SizedBox(height: AppSpace.sm),
                _SummaryCard(
                    subtotal: cart.subtotal,
                    address: _address,
                    error: _error,
                    timedOut: _timedOut,
                    active: _active,
                    onCheckout: _checkout),
              ],
            );
          }
          return Padding(
            padding: const EdgeInsets.all(AppSpace.xl),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: lines.isEmpty
                      ? const EmptyView(
                          message: 'Your cart is empty.',
                          icon: Icons.shopping_bag_outlined)
                      : ListView(
                          children: [
                            for (final line in lines)
                              Padding(
                                padding: const EdgeInsets.only(bottom: 12),
                                child: _CartLineCard(line: line),
                              ),
                          ],
                        ),
                ),
                const SizedBox(width: AppSpace.xxl),
                SizedBox(
                  width: 380,
                  child: SingleChildScrollView(
                    child: _SummaryCard(
                        subtotal: cart.subtotal,
                        address: _address,
                        error: _error,
                        timedOut: _timedOut,
                        active: _active,
                        onCheckout: _checkout),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _CartLineCard extends ConsumerWidget {
  final CartLine line;
  const _CartLineCard({required this.line});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Row(
          children: [
            RemoteImage(
              url: line.item.imageUrl,
              width: 64,
              height: 64,
              radius: AppRadius.sm,
              fallbackIcon: Icons.restaurant_menu_rounded,
            ),
            const SizedBox(width: AppSpace.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(line.item.name, style: theme.textTheme.titleSmall),
                  const SizedBox(height: 4),
                  Text(
                    formatMinor(line.item.priceMinor, line.item.currency),
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: AppColors.inkMuted),
                  ),
                  const SizedBox(height: 8),
                  QuantityStepper(
                    quantity: line.quantity,
                    onDecrement: () => ref
                        .read(cartProvider.notifier)
                        .changeQuantity(line.item.id, -1),
                    onIncrement: () => ref
                        .read(cartProvider.notifier)
                        .changeQuantity(line.item.id, 1),
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppSpace.sm),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  formatMinor(line.lineTotal, line.item.currency),
                  style: theme.textTheme.titleSmall
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline_rounded),
                  tooltip: 'Remove ${line.item.name}',
                  onPressed: () =>
                      ref.read(cartProvider.notifier).remove(line.item.id),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final int subtotal;
  final TextEditingController address;
  final String? error;
  final bool timedOut;
  final bool active;
  final VoidCallback onCheckout;

  const _SummaryCard({
    required this.subtotal,
    required this.address,
    required this.error,
    required this.timedOut,
    required this.active,
    required this.onCheckout,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.xl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Order summary', style: theme.textTheme.titleMedium),
            const SizedBox(height: AppSpace.lg),
            Row(
              children: [
                Expanded(
                  child: Text('Subtotal',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium
                          ?.copyWith(color: AppColors.inkMuted)),
                ),
                const SizedBox(width: AppSpace.md),
                Expanded(
                  child: Text(formatMinor(subtotal, 'INR'),
                      maxLines: 1,
                      textAlign: TextAlign.right,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w700)),
                ),
              ],
            ),
            const SizedBox(height: AppSpace.lg),
            TextField(
              controller: address,
              decoration: const InputDecoration(
                  labelText: 'Delivery address',
                  hintText: '12 Lake Road, Bengaluru',
                  prefixIcon: Icon(Icons.location_on_outlined)),
              maxLines: 2,
              minLines: 1,
            ),
            if (error != null) ...[
              const SizedBox(height: AppSpace.md),
              Row(
                children: [
                  const Icon(Icons.error_outline_rounded,
                      size: 18, color: AppColors.error),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(error!,
                        style: theme.textTheme.bodySmall
                            ?.copyWith(color: AppColors.error)),
                  ),
                ],
              ),
            ],
            if (timedOut) ...[
              const SizedBox(height: AppSpace.md),
              Container(
                padding: const EdgeInsets.all(AppSpace.md),
                decoration: BoxDecoration(
                  color: AppColors.amberSoft,
                  borderRadius: AppRadius.brSm,
                ),
                child: Text(
                    'The request timed out. The order may already exist: retrying uses the same key and never creates a duplicate.',
                    style: theme.textTheme.bodySmall),
              ),
            ],
            const SizedBox(height: AppSpace.lg),
            FilledButton(
              onPressed: active ? null : onCheckout,
              child: Text(active
                  ? 'Placing order…'
                  : timedOut
                      ? 'Retry with same key'
                      : 'Place order'),
            ),
          ],
        ),
      ),
    );
  }
}

class OrderAckScreen extends StatelessWidget {
  final Map<String, dynamic> accepted;
  const OrderAckScreen({super.key, required this.accepted});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ResponsiveScaffold(
      title: 'Order accepted',
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpace.xxl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(AppSpace.xxl),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 84,
                      height: 84,
                      decoration: const BoxDecoration(
                        color: AppColors.greenSoft,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.check_rounded,
                          size: 44, color: AppColors.green),
                    ),
                    const SizedBox(height: AppSpace.xl),
                    Text('Order accepted', style: theme.textTheme.headlineSmall),
                    const SizedBox(height: 6),
                    Text('We’ve sent it to the kitchen.',
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(color: AppColors.inkMuted)),
                    const SizedBox(height: AppSpace.xl),
                    _AckRow(label: 'Order ID', value: '${accepted['order_id']}'),
                    const Divider(height: 24),
                    _AckRow(
                        label: 'Status', value: '${accepted['status']}'),
                    const Divider(height: 24),
                    _AckRow(
                        label: 'Accepted total',
                        value: formatMinor(
                            (accepted['total'] ?? 0) as int,
                            (accepted['currency'] ?? 'INR') as String)),
                    const SizedBox(height: AppSpace.xl),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: () => Navigator.of(context)
                            .pushReplacementNamed(
                                '/order', arguments: accepted['order_id']),
                        icon: const Icon(Icons.local_shipping_outlined),
                        label: const Text('Track order'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _AckRow extends StatelessWidget {
  final String label;
  final String value;
  const _AckRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label,
            style: theme.textTheme.bodyMedium
                ?.copyWith(color: AppColors.inkMuted)),
        Flexible(
          child: Text(value,
              textAlign: TextAlign.right,
              style: theme.textTheme.titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }
}
