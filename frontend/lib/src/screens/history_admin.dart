// Paginated order history + read-only admin overview.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../widgets/app_scaffold.dart';

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
    Widget content;
    if (_loading) {
      content = const LoadingView();
    } else if (_error != null && _items.isEmpty) {
      content = ErrorView(message: _error!, onRetry: _refresh);
    } else if (_items.isEmpty) {
      content = const EmptyView(message: 'No orders yet.');
    } else {
      content = RefreshIndicator(
        onRefresh: _refresh,
        child: ListView.builder(
          itemCount: _items.length + 1,
          itemBuilder: (context, i) {
            if (i == _items.length) {
              if (_items.length >= _total) {
                return const SizedBox.shrink();
              }
              return TextButton(
                onPressed: _loadingMore
                    ? null
                    : () {
                        setState(() {
                          _page++;
                          _loadingMore = true;
                        });
                        _fetch();
                      },
                child: Text(_loadingMore ? 'Loading…' : 'Load more'),
              );
            }
            final o = _items[i];
            return ListTile(
              title: Text(o.id),
              subtitle: Text(
                  '${o.status} · ${formatMinor(o.totalMinor, o.currency)}'),
              onTap: () => Navigator.of(context)
                  .pushNamed('/order', arguments: o.id),
            );
          },
        ),
      );
    }
    return ResponsiveScaffold(title: 'Order history', body: content);
  }
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
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final s in adminStatuses)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
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
                        ? const EmptyView(message: 'No orders match.')
                        : ListView.builder(
                            itemCount: _items.length,
                            itemBuilder: (context, i) {
                              final o = _items[i];
                              return ListTile(
                                title: Text(o.id),
                                subtitle: Text(
                                    '${o.status} · ${formatMinor(o.totalMinor, o.currency)}'),
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }
}
