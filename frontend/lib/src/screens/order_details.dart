// Order details: status header, timeline, driver, notifications, failure
// explanation. Polls ~2s while visible; stops on terminal/dispose.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/app_scaffold.dart';
import '../widgets/ui.dart';

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
  // Captured in initState: `ref` is no longer usable during dispose(), so the
  // poller must be stopped through a stable reference to avoid throwing when
  // the user navigates away from tracking.
  late final OrderPoller _poller;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _poller = ref.read(orderPollerProvider.notifier);
    Future.microtask(() => _poller.start(widget.orderId));
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
    _poller.stop();
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
          final driverId = body['driver_id'] as String?;
          return RefreshIndicator(
            onRefresh: () async {
              ref.read(orderPollerProvider.notifier).start(widget.orderId);
              await _loadExtras();
            },
            child: ContentWidth(
              maxWidth: 820,
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
              child: ListView(
                children: [
                  _StatusHeader(
                      status: status,
                      total: formatMinor(
                          (body['total_minor'] ?? 0) as int,
                          (body['currency'] ?? 'INR') as String),
                      driverId: driverId),
                  const SizedBox(height: AppSpace.lg),
                  if (failure.isNotEmpty)
                    Container(
                      padding: const EdgeInsets.all(AppSpace.lg),
                      decoration: BoxDecoration(
                        color: AppColors.errorSoft,
                        borderRadius: AppRadius.brMd,
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline_rounded,
                              color: AppColors.error),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(failure,
                                style: Theme.of(context)
                                    .textTheme
                                    .bodyMedium
                                    ?.copyWith(color: AppColors.error)),
                          ),
                        ],
                      ),
                    ),
                  const SizedBox(height: AppSpace.lg),
                  _Panel(
                    title: 'Timeline',
                    child: _history.isEmpty
                        ? Text('No updates yet.',
                            style: Theme.of(context).textTheme.bodySmall)
                        : Column(
                            children: [
                              for (var i = 0; i < _history.length; i++)
                                _TimelineRow(
                                  entry: _history[i],
                                  isLast: i == _history.length - 1,
                                ),
                            ],
                          ),
                  ),
                  const SizedBox(height: AppSpace.lg),
                  _Panel(
                    title: 'Notifications',
                    child: _notifications.isEmpty
                        ? Text('No notifications yet.',
                            style: Theme.of(context).textTheme.bodySmall)
                        : Column(
                            children: [
                              for (final n in _notifications)
                                ListTile(
                                  contentPadding: EdgeInsets.zero,
                                  leading: const CircleAvatar(
                                    backgroundColor: AppColors.primarySoft,
                                    child: Icon(Icons.notifications_none_rounded,
                                        color: AppColors.primary, size: 20),
                                  ),
                                  title: Text('${n['title'] ?? ''}'),
                                  subtitle: Text('${n['body'] ?? ''}'),
                                ),
                            ],
                          ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _StatusHeader extends StatelessWidget {
  final String status;
  final String total;
  final String? driverId;

  const _StatusHeader(
      {required this.status, required this.total, required this.driverId});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return WarmPanel(
      padding: const EdgeInsets.all(AppSpace.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Semantics(
                label: 'Order status $status',
                child: StatusPill(status: status),
              ),
              const Spacer(),
              Text('Status: $status', style: theme.textTheme.bodySmall),
            ],
          ),
          const SizedBox(height: AppSpace.lg),
          Text('Order total', style: theme.textTheme.bodySmall),
          const SizedBox(height: 2),
          Text(total, style: theme.textTheme.headlineSmall),
          if (driverId != null) ...[
            const SizedBox(height: AppSpace.md),
            Row(
              children: [
                const CircleAvatar(
                  radius: 18,
                  backgroundColor: AppColors.primarySoft,
                  child: Icon(Icons.delivery_dining_rounded,
                      size: 20, color: AppColors.primary),
                ),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Driver assigned', style: theme.textTheme.bodySmall),
                    Text(driverId!, style: theme.textTheme.titleSmall),
                  ],
                ),
              ],
            ),
          ],
          const SizedBox(height: AppSpace.lg),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton.icon(
              key: const Key('orderMore'),
              onPressed: () => Navigator.of(context)
                  .pushNamedAndRemoveUntil('/restaurants', (route) => false),
              icon: const Icon(Icons.restaurant_menu_rounded),
              label: const Text('Order More'),
            ),
          ),
        ],
      ),
    );
  }
}

class _TimelineRow extends StatelessWidget {
  final Map<String, dynamic> entry;
  final bool isLast;

  const _TimelineRow({required this.entry, required this.isLast});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final from = entry['from_status'] ?? '—';
    final to = entry['to_status'];
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              const SizedBox(height: 3),
              Container(
                width: 12,
                height: 12,
                decoration: const BoxDecoration(
                  color: AppColors.primary,
                  shape: BoxShape.circle,
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: AppColors.border,
                  ),
                ),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: AppSpace.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('$from → $to',
                      style: theme.textTheme.titleSmall),
                  Text('version ${entry['order_version']}',
                      style: theme.textTheme.bodySmall),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  final String title;
  final Widget child;
  const _Panel({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.xl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: AppSpace.md),
            child,
          ],
        ),
      ),
    );
  }
}
