// Order details: timeline, driver, notifications, failure explanation.
// Polls ~2s while visible; stops on terminal/dispose.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../widgets/app_scaffold.dart';

class OrderDetailsScreen extends ConsumerStatefulWidget {
  final String orderId;
  const OrderDetailsScreen({super.key, required this.orderId});

  @override
  ConsumerState<OrderDetailsScreen> createState() => _OrderDetailsScreenState();
}

class _OrderDetailsScreenState extends ConsumerState<OrderDetailsScreen>
    with WidgetsBindingObserver {
  List<Map<String, dynamic>> _history = [];
  List<Map<String, dynamic>> _notifications = [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    Future.microtask(
        () => ref.read(orderPollerProvider.notifier).start(widget.orderId));
    _loadExtras();
  }

  Future<void> _loadExtras() async {
    final api = ref.read(apiClientProvider);
    try {
      final history =
          await api.getJson('/api/v1/orders/${widget.orderId}/history');
      final notifs = await api.getJson(
          '/api/v1/orders/${widget.orderId}/notifications',
          query: {'page': '1', 'page_size': '50'});
      if (!mounted) return;
      setState(() {
        _history = ((history is List ? history : (history['items'] ?? [])) as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        _notifications = ((notifs['items'] ?? []) as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      });
    } on ApiException catch (err) {
      if (err.isAuthExpired && mounted) {
        ref.read(sessionProvider.notifier).signOut();
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Stop polling when backgrounded; refresh when resumed.
    final poller = ref.read(orderPollerProvider.notifier);
    if (state == AppLifecycleState.paused) {
      poller.stop();
    } else if (state == AppLifecycleState.resumed) {
      poller.start(widget.orderId);
      _loadExtras();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    ref.read(orderPollerProvider.notifier).stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final order = ref.watch(orderPollerProvider);
    return ResponsiveScaffold(
      title: 'Order ${widget.orderId}',
      body: order.when(
        loading: () => const LoadingView(),
        error: (err, _) {
          final apiErr = err is ApiException ? err : null;
          if (apiErr?.status == 404) {
            return const EmptyView(message: 'Order not found.');
          }
          if (apiErr?.isAuthExpired == true) {
            return const EmptyView(
                message: 'Session expired. Please sign in again.');
          }
          return ErrorView(
              message: 'Could not load order. ${apiErr?.message ?? ''}',
              onRetry: () => ref
                  .read(orderPollerProvider.notifier)
                  .start(widget.orderId));
        },
        data: (body) {
          final status = (body['status'] ?? '') as String;
          final failure = failureExplanation(
              body['failure_code'] as String?, status);
          return RefreshIndicator(
            onRefresh: () async {
              ref.read(orderPollerProvider.notifier).start(widget.orderId);
              await _loadExtras();
            },
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Semantics(
                  label: 'Order status $status',
                  child: Text('Status: $status',
                      style: Theme.of(context).textTheme.titleLarge),
                ),
                Text(
                    'Total: ${formatMinor((body['total_minor'] ?? 0) as int, (body['currency'] ?? 'INR') as String)}'),
                if ((body['driver_id'] as String?) != null)
                  Text('Driver: ${body['driver_id']}'),
                if (failure.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text(failure,
                        style: const TextStyle(color: Colors.red)),
                  ),
                const Divider(),
                const Text('Timeline'),
                for (final h in _history)
                  ListTile(
                    dense: true,
                    title: Text(
                        '${h['from_status'] ?? '—'} → ${h['to_status']}'),
                    subtitle: Text('v${h['order_version']}'),
                  ),
                const Divider(),
                const Text('Notifications'),
                for (final n in _notifications)
                  ListTile(
                    dense: true,
                    title: Text((n['title'] ?? '') as String),
                    subtitle: Text((n['body'] ?? '') as String),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}
