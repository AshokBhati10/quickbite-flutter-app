// Restaurant list + menu screens.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../widgets/app_scaffold.dart';

class RestaurantListScreen extends ConsumerStatefulWidget {
  const RestaurantListScreen({super.key});

  @override
  ConsumerState<RestaurantListScreen> createState() =>
      _RestaurantListScreenState();
}

class _RestaurantListScreenState extends ConsumerState<RestaurantListScreen> {
  List<Restaurant> _items = [];
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
      final body = await ref
          .read(apiClientProvider)
          .getJson('/api/v1/restaurants', query: {'page': '1', 'page_size': '50'});
      final items = (body['items'] as List)
          .map((e) => Restaurant.fromJson(e as Map<String, dynamic>))
          .toList();
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } on ApiException catch (err) {
      if (!mounted) return;
      if (err.isAuthExpired) {
        ref.read(sessionProvider.notifier).signOut();
        return;
      }
      setState(() {
        _error = err.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    Widget content;
    if (_loading) {
      content = const LoadingView();
    } else if (_error != null) {
      content = ErrorView(message: _error!, onRetry: _load);
    } else if (_items.isEmpty) {
      content = const EmptyView(message: 'No restaurants available yet.');
    } else {
      content = RefreshIndicator(
        onRefresh: _load,
        child: ListView.builder(
          itemCount: _items.length,
          itemBuilder: (context, i) {
            final r = _items[i];
            return Semantics(
              label: 'Restaurant ${r.name}',
              child: ListTile(
                title: Text(r.name),
                subtitle: Text(r.description),
                onTap: () => Navigator.of(context)
                    .pushNamed('/menu', arguments: r),
              ),
            );
          },
        ),
      );
    }
    return ResponsiveScaffold(
      title: 'Restaurants',
      actions: [
        if (ref.watch(sessionProvider)?.role == 'admin')
          IconButton(
            icon: const Icon(Icons.admin_panel_settings),
            tooltip: 'Admin overview',
            onPressed: () => Navigator.of(context).pushNamed('/admin'),
          ),
        IconButton(
          icon: const Icon(Icons.history),
          tooltip: 'Order history',
          onPressed: () => Navigator.of(context).pushNamed('/history'),
        ),
      ],
      body: content,
    );
  }
}

class MenuScreen extends ConsumerStatefulWidget {
  final Restaurant restaurant;
  const MenuScreen({super.key, required this.restaurant});

  @override
  ConsumerState<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends ConsumerState<MenuScreen> {
  List<MenuItem> _items = [];
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
      final body = await ref.read(apiClientProvider).getJson(
          '/api/v1/restaurants/${widget.restaurant.id}/menu',
          query: {'page': '1', 'page_size': '100'});
      final items = (body['items'] as List)
          .map((e) => MenuItem.fromJson(e as Map<String, dynamic>))
          .toList();
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } on ApiException catch (err) {
      if (!mounted) return;
      if (err.isAuthExpired) {
        ref.read(sessionProvider.notifier).signOut();
        return;
      }
      setState(() {
        _error = err.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    Widget content;
    if (_loading) {
      content = const LoadingView();
    } else if (_error != null) {
      content = ErrorView(message: _error!, onRetry: _load);
    } else if (_items.isEmpty) {
      content = const EmptyView(message: 'This menu is empty.');
    } else {
      content = ListView.builder(
        itemCount: _items.length,
        itemBuilder: (context, i) {
          final m = _items[i];
          return ListTile(
            title: Text(m.name),
            subtitle: Text(
                '${formatMinor(m.priceMinor, m.currency)}${m.isActive ? '' : ' (unavailable)'}'),
            trailing: m.isActive
                ? IconButton(
                    icon: const Icon(Icons.add_shopping_cart),
                    tooltip: 'Add ${m.name} to cart',
                    onPressed: () {
                      ref.read(cartProvider.notifier).add(m, 1);
                      ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('${m.name} added to cart')));
                    },
                  )
                : null,
          );
        },
      );
    }
    return ResponsiveScaffold(
      title: widget.restaurant.name,
      actions: [
        IconButton(
          icon: const Icon(Icons.shopping_cart),
          tooltip: 'Open cart',
          onPressed: () => Navigator.of(context).pushNamed('/cart'),
        ),
      ],
      body: content,
    );
  }
}
