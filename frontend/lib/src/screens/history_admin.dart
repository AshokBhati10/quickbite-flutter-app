// My Orders (real order history) + read-only admin overview.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/app_scaffold.dart';
import '../widgets/ui.dart';

class OrderHistoryScreen extends ConsumerStatefulWidget {
  const OrderHistoryScreen({super.key});

  @override
  ConsumerState<OrderHistoryScreen> createState() => _OrderHistoryScreenState();
}

class _OrderHistoryScreenState extends ConsumerState<OrderHistoryScreen> {
  final List<OrderSummary> _items = [];
  int _page = 1;
  int _total = 0;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    if (ref.read(sessionProvider) == null) return;
    setState(() {
      _loading = true;
      _error = null;
      _page = 1;
    });
    await _fetch(reset: true);
  }

  Future<void> _fetch({bool reset = false}) async {
    try {
      final body = await ref.read(apiClientProvider).getJson('/api/v1/orders',
          query: {'page': '$_page', 'page_size': '20'});
      final items = (body['items'] as List)
          .map((e) => OrderSummary.fromJson(e as Map<String, dynamic>))
          .toList();
      if (!mounted) return;
      setState(() {
        if (reset) _items.clear();
        _items.addAll(items);
        _total = (body['total'] ?? 0) as int;
        _loading = false;
        _loadingMore = false;
      });
    } on ApiException catch (err) {
      if (!mounted) return;
      if (err.isAuthExpired) {
        ref.read(sessionProvider.notifier).signOut();
        return;
      }
      setState(() {
        _error = err.code == 'network_error' || err.code == 'timeout'
            ? 'You appear to be offline. Pull to refresh when reconnected.'
            : err.message;
        _loading = false;
        _loadingMore = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (ref.watch(sessionProvider) == null) {
      return const NavScaffold(
        body: Center(child: Text('Please sign in to view your orders.')),
      );
    }
    Widget content;
    if (_loading) {
      content = const LoadingView();
    } else if (_error != null && _items.isEmpty) {
      content = ErrorView(message: _error!, onRetry: _refresh);
    } else if (_items.isEmpty) {
      content = const _NoOrders();
    } else {
      content = RefreshIndicator(
        onRefresh: _refresh,
        child: ContentWidth(
          maxWidth: 900,
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          child: ListView.builder(
            itemCount: _items.length + 2,
            itemBuilder: (context, i) {
              if (i == 0) {
                return const Padding(
                  padding: EdgeInsets.only(bottom: AppSpace.md),
                  child: SectionHeading(
                    title: 'My Orders',
                    subtitle: 'Everything you’ve ordered so far',
                  ),
                );
              }
              if (i == _items.length + 1) {
                if (_items.length >= _total) return const SizedBox.shrink();
                return Center(
                  child: TextButton.icon(
                    onPressed: _loadingMore
                        ? null
                        : () {
                            setState(() {
                              _page++;
                              _loadingMore = true;
                            });
                            _fetch();
                          },
                    icon: const Icon(Icons.expand_more_rounded, size: 18),
                    label: Text(_loadingMore ? 'Loading…' : 'Load more'),
                  ),
                );
              }
              return _OrderCard(order: _items[i - 1]);
            },
          ),
        ),
      );
    }
    return NavScaffold(body: content);
  }
}

class _NoOrders extends StatelessWidget {
  const _NoOrders();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: const BoxDecoration(
              color: AppColors.surfaceWarm,
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.receipt_long_rounded,
                size: 34, color: AppColors.inkMuted),
          ),
          const SizedBox(height: AppSpace.lg),
          Text('No orders yet', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text('Your past orders will appear here.',
              style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: AppSpace.xl),
          FilledButton.icon(
            onPressed: () => Navigator.of(context)
                .pushNamedAndRemoveUntil('/restaurants', (_) => false),
            icon: const Icon(Icons.storefront_rounded),
            label: const Text('Browse Restaurants'),
          ),
        ],
      ),
    );
  }
}

class _OrderCard extends StatelessWidget {
  final OrderSummary order;
  const _OrderCard({required this.order});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.md),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          order.restaurantName.isNotEmpty
                              ? order.restaurantName
                              : 'Restaurant',
                          style: theme.textTheme.titleMedium,
                        ),
                        const SizedBox(height: 2),
                        Text('Order ${order.id}',
                            style: theme.textTheme.bodySmall),
                      ],
                    ),
                  ),
                  StatusPill(status: order.status),
                ],
              ),
              const SizedBox(height: AppSpace.sm),
              Row(
                children: [
                  const Icon(Icons.schedule_rounded,
                      size: 16, color: AppColors.inkMuted),
                  const SizedBox(width: 6),
                  Text(_formatDateTime(order.createdAt),
                      style: theme.textTheme.bodySmall),
                ],
              ),
              if (order.lines.isNotEmpty) ...[
                const Divider(height: 24),
                for (final line in order.lines)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 2),
                    child: Text('${line.quantity} × ${line.name}',
                        style: theme.textTheme.bodyMedium),
                  ),
              ],
              const Divider(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Total',
                      style: theme.textTheme.bodyMedium
                          ?.copyWith(color: AppColors.inkMuted)),
                  Text(formatMinor(order.totalMinor, order.currency),
                      style: theme.textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w700)),
                ],
              ),
              const SizedBox(height: AppSpace.sm),
              Align(
                alignment: Alignment.centerRight,
                child: OutlinedButton.icon(
                  onPressed: () => Navigator.of(context)
                      .pushNamed('/order', arguments: order.id),
                  icon: const Icon(Icons.visibility_outlined, size: 18),
                  label: const Text('View Details'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

String _formatDateTime(DateTime? dt) {
  if (dt == null) return 'Date unknown';
  final local = dt.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${local.year}-${two(local.month)}-${two(local.day)} '
      '${two(local.hour)}:${two(local.minute)}';
}

const adminStatuses = [
  'ALL',
  'PENDING',
  'PAID',
  'CONFIRMED',
  'DRIVER_ASSIGNED',
  'PAYMENT_FAILED',
  'FAILED'
];

class AdminOverviewScreen extends ConsumerStatefulWidget {
  const AdminOverviewScreen({super.key});

  @override
  ConsumerState<AdminOverviewScreen> createState() =>
      _AdminOverviewScreenState();
}

class _AdminOverviewScreenState extends ConsumerState<AdminOverviewScreen> {
  String _filter = 'ALL';
  final List<OrderSummary> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final query = {'page': '1', 'page_size': '20'};
      if (_filter != 'ALL') query['status'] = _filter;
      final body = await ref
          .read(apiClientProvider)
          .getJson('/api/v1/admin/orders', query: query);
      final items = (body['items'] as List)
          .map((e) => OrderSummary.fromJson(e as Map<String, dynamic>))
          .toList();
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(items);
        _loading = false;
      });
    } on ApiException catch (err) {
      if (!mounted) return;
      setState(() {
        _error = err.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return ResponsiveScaffold(
      title: 'Admin overview (read-only)',
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: 52,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              children: [
                for (final s in adminStatuses)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(s),
                      selected: _filter == s,
                      onSelected: (_) {
                        setState(() => _filter = s);
                        _load();
                      },
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const LoadingView()
                : _error != null
                    ? ErrorView(message: _error!, onRetry: _load)
                    : _items.isEmpty
                        ? const EmptyView(
                            message: 'No orders match.',
                            icon: Icons.inbox_outlined)
                        : ContentWidth(
                            maxWidth: 900,
                            padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                            child: ListView.builder(
                              itemCount: _items.length,
                              itemBuilder: (context, i) {
                                final o = _items[i];
                                return Padding(
                                  padding:
                                      const EdgeInsets.only(bottom: AppSpace.md),
                                  child: Card(
                                    child: Padding(
                                      padding: const EdgeInsets.all(AppSpace.lg),
                                      child: Row(
                                        children: [
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment:
                                                  CrossAxisAlignment.start,
                                              children: [
                                                Text(o.id,
                                                    style: Theme.of(context)
                                                        .textTheme
                                                        .titleSmall),
                                                const SizedBox(height: 4),
                                                Text(
                                                    formatMinor(o.totalMinor,
                                                        o.currency),
                                                    style: Theme.of(context)
                                                        .textTheme
                                                        .bodySmall),
                                              ],
                                            ),
                                          ),
                                          StatusPill(status: o.status),
                                        ],
                                      ),
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }
}
