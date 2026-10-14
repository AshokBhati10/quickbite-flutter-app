// Restaurant discovery home (hero, search, cuisine filters, paginated cards)
// and the restaurant menu (banner header, categorized item cards).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/app_navbar.dart';
import '../widgets/app_scaffold.dart';
import '../widgets/media.dart';
import '../widgets/ui.dart';

const int kRestaurantsPerPage = 5;
const double _maxContentWidth = 1180;

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
  int _page = 1;
  int _total = 0;
  List<String> _cuisines = [];
  String _cuisine = '';
  Timer? _debounce;

  int get _pageCount {
    final pages = (_total / kRestaurantsPerPage).ceil();
    return pages < 1 ? 1 : pages;
  }

  @override
  void initState() {
    super.initState();
    _loadCuisines();
    _load(1);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  Future<void> _loadCuisines() async {
    try {
      final body = await ref
          .read(apiClientProvider)
          .getJson('/api/v1/restaurants/cuisines');
      final items = ((body['items'] ?? []) as List)
          .map((e) => e.toString())
          .where((e) => e.isNotEmpty)
          .toList();
      if (mounted) setState(() => _cuisines = items);
    } on ApiException {
      // Filters are a progressive enhancement; browsing still works without.
    }
  }

  Future<void> _load(int page) async {
    if (ref.read(sessionProvider) == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    final q = ref.read(restaurantQueryProvider).trim();
    final query = <String, String>{
      'page': '$page',
      'page_size': '$kRestaurantsPerPage',
    };
    if (q.isNotEmpty) query['q'] = q;
    if (_cuisine.isNotEmpty) query['cuisine'] = _cuisine;
    try {
      final body = await ref
          .read(apiClientProvider)
          .getJson('/api/v1/restaurants', query: query);
      final items = (body['items'] as List)
          .map((e) => Restaurant.fromJson(e as Map<String, dynamic>))
          .toList();
      if (!mounted) return;
      setState(() {
        _items = items;
        _page = page;
        _total = (body['total'] ?? items.length) as int;
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

  void _onQueryChanged(String value) {
    // Debounce so typing does not hammer the API on every keystroke.
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (mounted) _load(1);
    });
  }

  void _selectCuisine(String value) {
    setState(() => _cuisine = value);
    _load(1);
  }

  bool get _filtering =>
      _cuisine.isNotEmpty ||
      ref.read(restaurantQueryProvider).trim().isNotEmpty;

  @override
  Widget build(BuildContext context) {
    ref.listen<String>(restaurantQueryProvider, (previous, next) {
      if (previous != next) _onQueryChanged(next);
    });
    if (ref.watch(sessionProvider) == null) {
      return const NavScaffold(body: _SignInRequired());
    }
    return NavScaffold(
      body: Column(
        children: [
          _hero(context),
          Expanded(child: _content()),
          if (!_loading && _error == null && _items.isNotEmpty)
            _PaginationBar(
              page: _page,
              pageCount: _pageCount,
              onPrevious: _page > 1 ? () => _load(_page - 1) : null,
              onNext: _page < _pageCount ? () => _load(_page + 1) : null,
            ),
        ],
      ),
    );
  }

  Widget _hero(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    final narrow = width < kWideBreakpoint;
    return ContentWidth(
      maxWidth: _maxContentWidth,
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
      child: SizedBox(
        width: double.infinity,
        child: WarmPanel(
          gradient: const [AppColors.primarySoft, AppColors.amberSoft],
          borderRadius: AppRadius.brXl,
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const InfoPill(
                icon: Icons.place_rounded,
                label: 'Local kitchens, delivered fast',
                color: AppColors.primaryDark,
              ),
              const SizedBox(height: 14),
              Text('Discover Restaurants',
                  style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 4),
              Text(
                'Browse menus from local kitchens and order in a few taps.',
                style: Theme.of(context)
                    .textTheme
                    .bodyLarge
                    ?.copyWith(color: AppColors.inkMuted),
              ),
              // On wide screens the navbar already shows the search field.
              if (narrow) ...[
                const SizedBox(height: AppSpace.lg),
                RestaurantSearchField(
                  key: const Key('heroSearch'),
                  focusNode: ref.read(restaurantSearchFocusProvider),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _cuisineFilters() {
    return SizedBox(
      height: 48,
      child: ListView(
        scrollDirection: Axis.horizontal,
        children: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              avatar: _cuisine.isEmpty
                  ? null
                  : const Icon(Icons.grid_view_rounded, size: 16),
              label: const Text('All'),
              selected: _cuisine.isEmpty,
              onSelected: (_) => _selectCuisine(''),
            ),
          ),
          for (final cuisine in _cuisines)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                label: Text(cuisine),
                selected: _cuisine == cuisine,
                onSelected: (_) => _selectCuisine(cuisine),
              ),
            ),
        ],
      ),
    );
  }

  Widget _content() {
    if (_loading) return const LoadingView();
    if (_error != null) {
      return ErrorView(message: _error!, onRetry: () => _load(_page));
    }
    if (_items.isEmpty) {
      return _EmptyResults(
        filtering: _filtering,
        onClear: () {
          ref.read(restaurantQueryProvider.notifier).state = '';
          _selectCuisine('');
        },
      );
    }
    return _grid();
  }

  Widget _grid() {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: _maxContentWidth),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
              child: SectionHeading(
                title: 'Restaurants',
                subtitle: '$_total kitchens ready to cook',
              ),
            ),
            if (_cuisines.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
                child: _cuisineFilters(),
              ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: () => _load(_page),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    // Responsive: one column on phones, more as width grows.
                    final maxExtent = constraints.maxWidth < 520
                        ? constraints.maxWidth
                        : (constraints.maxWidth < 900 ? 380.0 : 340.0);
                    return GridView.builder(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
                      physics: const AlwaysScrollableScrollPhysics(),
                      gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
                        maxCrossAxisExtent: maxExtent,
                        mainAxisExtent: 296,
                        crossAxisSpacing: 16,
                        mainAxisSpacing: 16,
                      ),
                      itemCount: _items.length,
                      itemBuilder: (context, i) => _RestaurantCard(
                        restaurant: _items[i],
                        onTap: () => Navigator.of(context)
                            .pushNamed('/menu', arguments: _items[i]),
                      ),
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyResults extends StatelessWidget {
  final bool filtering;
  final VoidCallback onClear;

  const _EmptyResults({required this.filtering, required this.onClear});

  @override
  Widget build(BuildContext context) {
    if (!filtering) {
      return const EmptyView(
          message: 'No restaurants available yet.',
          icon: Icons.storefront_outlined);
    }
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(
              color: AppColors.surfaceWarm,
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.search_off_rounded,
                size: 30, color: AppColors.inkMuted),
          ),
          const SizedBox(height: AppSpace.lg),
          const Text('No restaurants match your search.'),
          const SizedBox(height: AppSpace.sm),
          OutlinedButton(onPressed: onClear, child: const Text('Clear search')),
        ],
      ),
    );
  }
}

class _SignInRequired extends StatelessWidget {
  const _SignInRequired();

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
            child: const Icon(Icons.lock_outline_rounded,
                size: 32, color: AppColors.primary),
          ),
          const SizedBox(height: AppSpace.lg),
          Text('Please sign in to browse restaurants.',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: AppSpace.lg),
          FilledButton(
            onPressed: () => Navigator.of(context)
                .pushNamedAndRemoveUntil('/signin', (_) => false),
            child: const Text('Sign in'),
          ),
        ],
      ),
    );
  }
}

class _RestaurantCard extends StatelessWidget {
  final Restaurant restaurant;
  final VoidCallback onTap;

  const _RestaurantCard({required this.restaurant, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      label: 'Restaurant ${restaurant.name}',
      button: true,
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Stack(
                children: [
                  RemoteImage(
                    url: restaurant.imageUrl,
                    height: 148,
                    width: double.infinity,
                    radius: 0,
                    fallbackIcon: Icons.storefront_rounded,
                  ),
                  if (restaurant.cuisine.isNotEmpty)
                    Positioned(
                      left: 12,
                      top: 12,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 5),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.92),
                          borderRadius: AppRadius.brPill,
                          boxShadow: AppShadows.soft,
                        ),
                        child: Text(
                          restaurant.cuisine,
                          style: theme.textTheme.labelSmall
                              ?.copyWith(color: AppColors.primaryDark),
                        ),
                      ),
                    ),
                ],
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      restaurant.name,
                      style: theme.textTheme.titleMedium,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      restaurant.description,
                      style: theme.textTheme.bodySmall,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Text(
                          'View menu',
                          style: theme.textTheme.labelMedium
                              ?.copyWith(color: AppColors.primary),
                        ),
                        const SizedBox(width: 4),
                        const Icon(Icons.arrow_forward_rounded,
                            size: 16, color: AppColors.primary),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PaginationBar extends StatelessWidget {
  final int page;
  final int pageCount;
  final VoidCallback? onPrevious;
  final VoidCallback? onNext;

  const _PaginationBar({
    required this.page,
    required this.pageCount,
    required this.onPrevious,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.borderSoft)),
      ),
      child: SafeArea(
        top: false,
        child: ContentWidth(
          maxWidth: _maxContentWidth,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(
            children: [
              OutlinedButton.icon(
                onPressed: onPrevious,
                icon: const Icon(Icons.chevron_left_rounded, size: 18),
                label: const Text('Previous'),
              ),
              Expanded(
                child: Center(
                  child: Semantics(
                    label: 'Page $page of $pageCount',
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppColors.primarySoft,
                        borderRadius: AppRadius.brPill,
                      ),
                      child: Text(
                        'Page $page of $pageCount',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            color: AppColors.primaryDark,
                            fontWeight: FontWeight.w700),
                      ),
                    ),
                  ),
                ),
              ),
              FilledButton.icon(
                onPressed: onNext,
                icon: const Icon(Icons.chevron_right_rounded, size: 18),
                label: const Text('Next'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Menu
// ---------------------------------------------------------------------------

const List<String> _categoryOrder = [
  'Starters',
  'Main Course',
  'Sides',
  'Beverages',
  'Desserts',
];

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

  List<MapEntry<String, List<MenuItem>>> _sections() {
    final grouped = <String, List<MenuItem>>{};
    for (final item in _items) {
      final key = item.category.isEmpty ? 'Other' : item.category;
      grouped.putIfAbsent(key, () => []).add(item);
    }
    final ordered = <MapEntry<String, List<MenuItem>>>[];
    for (final category in _categoryOrder) {
      if (grouped.containsKey(category)) {
        ordered.add(MapEntry(category, grouped.remove(category)!));
      }
    }
    for (final entry in grouped.entries) {
      ordered.add(entry);
    }
    return ordered;
  }

  @override
  Widget build(BuildContext context) {
    Widget content;
    if (_loading) {
      content = const LoadingView();
    } else if (_error != null) {
      content = ErrorView(message: _error!, onRetry: _load);
    } else if (_items.isEmpty) {
      content = const EmptyView(
          message: 'This menu is empty.', icon: Icons.restaurant_menu_rounded);
    } else {
      final sections = _sections();
      content = ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          _MenuHeader(restaurant: widget.restaurant),
          const SizedBox(height: AppSpace.xl),
          for (final section in sections) ...[
            _CategoryHeader(title: section.key),
            const SizedBox(height: AppSpace.md),
            for (final item in section.value)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _MenuItemCard(
                  item: item,
                  onAdd: item.isActive
                      ? () {
                          ref.read(cartProvider.notifier).add(item, 1);
                          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                              content: Text('${item.name} added to cart')));
                        }
                      : null,
                ),
              ),
            const SizedBox(height: AppSpace.sm),
          ],
        ],
      );
    }
    // Uses the shared navbar so the cart badge is visible and updates live
    // as menu items are added.
    return NavScaffold(body: content);
  }
}

class _MenuHeader extends StatelessWidget {
  final Restaurant restaurant;
  const _MenuHeader({required this.restaurant});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Stack(
            children: [
              RemoteImage(
                url: restaurant.imageUrl,
                height: 190,
                width: double.infinity,
                radius: 0,
                fallbackIcon: Icons.storefront_rounded,
              ),
              Positioned(
                left: 16,
                right: 16,
                bottom: 14,
                child: Row(
                  children: [
                    if (restaurant.cuisine.isNotEmpty)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 5),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.92),
                          borderRadius: AppRadius.brPill,
                        ),
                        child: Text(
                          restaurant.cuisine,
                          style: theme.textTheme.labelSmall
                              ?.copyWith(color: AppColors.primaryDark),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpace.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(restaurant.name, style: theme.textTheme.headlineSmall),
                if (restaurant.description.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(restaurant.description,
                      style: theme.textTheme.bodyMedium
                          ?.copyWith(color: AppColors.inkMuted)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CategoryHeader extends StatelessWidget {
  final String title;
  const _CategoryHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 4,
          height: 20,
          decoration: BoxDecoration(
            color: AppColors.primary,
            borderRadius: AppRadius.brPill,
          ),
        ),
        const SizedBox(width: 10),
        Text(title, style: Theme.of(context).textTheme.titleLarge),
      ],
    );
  }
}

class _MenuItemCard extends StatelessWidget {
  final MenuItem item;
  final VoidCallback? onAdd;

  const _MenuItemCard({required this.item, required this.onAdd});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final soldOut = !item.isActive;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              children: [
                RemoteImage(
                  url: item.imageUrl,
                  width: 88,
                  height: 88,
                  radius: AppRadius.md,
                  fallbackIcon: Icons.restaurant_menu_rounded,
                ),
                if (soldOut)
                  Positioned.fill(
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.45),
                        borderRadius: AppRadius.brMd,
                      ),
                      child: const Center(
                        child: Text('Sold out',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                                fontSize: 12)),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(width: AppSpace.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(item.name, style: theme.textTheme.titleMedium),
                  if (item.description.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(item.description, style: theme.textTheme.bodySmall),
                  ],
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(
                        formatMinor(item.priceMinor, item.currency),
                        style: theme.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      if (!soldOut)
                        const InfoPill(
                            icon: Icons.check_circle_rounded,
                            label: 'Available',
                            color: AppColors.green)
                      else
                        const InfoPill(
                            icon: Icons.remove_circle_rounded,
                            label: 'Unavailable',
                            color: AppColors.error),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            if (!soldOut)
              PillIconButton(
                icon: Icons.add_shopping_cart_rounded,
                label: 'Add',
                tooltip: 'Add ${item.name} to cart',
                onPressed: onAdd,
              ),
          ],
        ),
      ),
    );
  }
}
