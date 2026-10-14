// Responsive top navigation: brand, links, search, cart badge, profile menu.
// Desktop shows inline controls; narrower screens collapse into a drawer.
// Styled by the shared design system (white bar, coral accents, pill controls).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/models.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import 'ui.dart';

const double kNavBarHeight = 66;
// Below this width the inline links/search collapse into a hamburger drawer;
// at or above it the full row is shown. Kept equal so tablet widths get the
// compact menu instead of an overflowing row.
const double kWideBreakpoint = 900;
const double kMediumBreakpoint = 900;

bool _isHomeRoute(BuildContext context) {
  final name = ModalRoute.of(context)?.settings.name;
  return name == null || name == '/' || name == '/restaurants';
}

/// Navigate to the app home, preserving nothing below it.
void goHome(BuildContext context, WidgetRef ref) {
  final authed = ref.read(sessionProvider) != null;
  Navigator.of(context).pushNamedAndRemoveUntil(
      authed ? '/restaurants' : '/signin', (_) => false);
}

/// Push a named route unless it is already the current one.
void pushOnce(BuildContext context, String name, {Object? arguments}) {
  if (ModalRoute.of(context)?.settings.name == name) return;
  Navigator.of(context).pushNamed(name, arguments: arguments);
}

class AppNavBar extends ConsumerWidget implements PreferredSizeWidget {
  const AppNavBar({super.key});

  @override
  Size get preferredSize => const Size.fromHeight(kNavBarHeight);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final width = MediaQuery.of(context).size.width;
    final narrow = width < kMediumBreakpoint;
    final wide = width >= kWideBreakpoint;
    final onHome = _isHomeRoute(context);
    // Exactly one search field is visible at a time: the navbar's on wide
    // screens, the home hero's on narrow screens.
    final showBarSearch = wide;

    return AppBar(
      automaticallyImplyLeading: false,
      primary: true,
      elevation: 0,
      scrolledUnderElevation: 0,
      toolbarHeight: kNavBarHeight,
      titleSpacing: narrow ? 8 : 20,
      title: Row(
        children: [
          if (Navigator.of(context).canPop())
            IconButton(
              icon: const Icon(Icons.arrow_back_rounded),
              tooltip: 'Back',
              onPressed: () => Navigator.of(context).maybePop(),
            ),
          if (narrow)
            Builder(
              builder: (ctx) => IconButton(
                icon: const Icon(Icons.menu_rounded),
                tooltip: 'Open menu',
                onPressed: () => Scaffold.of(ctx).openDrawer(),
              ),
            ),
          BrandMark(
            size: 34,
            showText: width >= 420,
            textColor: AppColors.primary,
            onTap: () => goHome(context, ref),
          ),
          if (!narrow) ...[
            const SizedBox(width: 20),
            _NavLink(
              label: 'Restaurants',
              icon: Icons.storefront_rounded,
              selected: onHome,
              onTap: () {
                if (ModalRoute.of(context)?.settings.name == '/restaurants') {
                  return;
                }
                goHome(context, ref);
              },
            ),
            _NavLink(
              label: 'My Orders',
              icon: Icons.receipt_long_rounded,
              selected: ModalRoute.of(context)?.settings.name == '/history',
              onTap: () => _openOrders(context, ref),
            ),
          ],
          const Spacer(),
          if (showBarSearch)
            Expanded(
              flex: 3,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: RestaurantSearchField(
                  key: const Key('navSearch'),
                  onSubmitted: (value) {
                    if (!onHome) goHome(context, ref);
                  },
                ),
              ),
            )
          else
            IconButton(
              icon: const Icon(Icons.search_rounded),
              tooltip: 'Search restaurants',
              onPressed: () {
                if (!onHome) {
                  goHome(context, ref);
                } else {
                  ref.read(restaurantSearchFocusProvider).requestFocus();
                }
              },
            ),
          const _CartButton(),
          const SizedBox(width: 2),
          _ProfileMenu(showName: wide),
          const SizedBox(width: 4),
        ],
      ),
    );
  }

  void _openOrders(BuildContext context, WidgetRef ref) {
    if (ref.read(sessionProvider) == null) {
      pushOnce(context, '/signin');
      return;
    }
    pushOnce(context, '/history');
  }
}

class _NavLink extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  const _NavLink({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.primary : AppColors.inkMuted;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Material(
        color: selected ? AppColors.primarySoft : Colors.transparent,
        borderRadius: AppRadius.brPill,
        child: InkWell(
          onTap: onTap,
          borderRadius: AppRadius.brPill,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 18, color: color),
                const SizedBox(width: 8),
                Text(
                  label,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: color,
                        fontWeight:
                            selected ? FontWeight.w700 : FontWeight.w600,
                      ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Cart icon with a live item-count badge from the shared cart state.
class _CartButton extends ConsumerWidget {
  const _CartButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final count = ref.watch(cartProvider).totalQuantity;
    return IconButton(
      // Tooltip key lets tests and screen readers identify the live count.
      tooltip: 'Cart count $count',
      onPressed: () => pushOnce(context, '/cart'),
      icon: Badge(
        // Always visible so the count reads 0, then 1, then 2 as items add.
        isLabelVisible: true,
        label: Text('$count', key: const Key('cartCount')),
        child: const Icon(Icons.shopping_bag_outlined),
      ),
    );
  }
}

class _ProfileMenu extends ConsumerWidget {
  final bool showName;
  const _ProfileMenu({required this.showName});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    if (session == null) {
      return PopupMenuButton<String>(
        tooltip: 'Account',
        onSelected: (value) {
          if (value == 'login') pushOnce(context, '/signin');
          if (value == 'register') pushOnce(context, '/register');
        },
        itemBuilder: (context) => const [
          PopupMenuItem(
            value: 'login',
            child: _MenuRow(icon: Icons.login_rounded, label: 'Log in'),
          ),
          PopupMenuItem(
            value: 'register',
            child: _MenuRow(icon: Icons.person_add_alt_1_rounded, label: 'Register'),
          ),
        ],
        child: const _AvatarTile(child: Icon(Icons.person_outline_rounded)),
      );
    }
    return PopupMenuButton<String>(
      tooltip: 'Account menu',
      onSelected: (value) => _onSelected(context, ref, value),
      itemBuilder: (context) => [
        PopupMenuItem<String>(
          enabled: false,
          child: _ProfileHeader(user: session),
        ),
        const PopupMenuDivider(),
        const PopupMenuItem(
          value: 'orders',
          child: _MenuRow(icon: Icons.receipt_long_rounded, label: 'My Orders'),
        ),
        const PopupMenuItem(
          value: 'profile',
          child: _MenuRow(
              icon: Icons.account_circle_outlined, label: 'Profile Details'),
        ),
        if (session.role == 'admin')
          const PopupMenuItem(
            value: 'admin',
            child: _MenuRow(
                icon: Icons.admin_panel_settings_outlined,
                label: 'Admin overview'),
          ),
        const PopupMenuDivider(),
        const PopupMenuItem(
          value: 'logout',
          child: _MenuRow(icon: Icons.logout_rounded, label: 'Logout'),
        ),
      ],
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _AvatarTile(
              child: Text(
                _initials(
                    session.name.isNotEmpty ? session.name : session.email),
                style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: Colors.white),
              ),
            ),
            if (showName) ...[
              const SizedBox(width: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 130),
                child: Text(
                  session.name.isNotEmpty ? session.name : session.email,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelLarge,
                ),
              ),
              const Icon(Icons.keyboard_arrow_down_rounded, size: 20),
            ],
          ],
        ),
      ),
    );
  }

  void _onSelected(BuildContext context, WidgetRef ref, String value) {
    switch (value) {
      case 'orders':
        pushOnce(context, '/history');
      case 'profile':
        pushOnce(context, '/profile');
      case 'admin':
        pushOnce(context, '/admin');
      case 'logout':
        ref.read(cartProvider.notifier).clear();
        final future = ref.read(sessionProvider.notifier).signOut();
        // Navigate immediately; token teardown continues in the background.
        Navigator.of(context).pushNamedAndRemoveUntil('/signin', (_) => false);
        future.ignore();
    }
  }
}

class _AvatarTile extends StatelessWidget {
  final Widget child;
  const _AvatarTile({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 34,
      height: 34,
      alignment: Alignment.center,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [AppColors.primary, Color(0xFFFF7A45)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        shape: BoxShape.circle,
      ),
      child: IconTheme(
        data: const IconThemeData(color: Colors.white, size: 20),
        child: child,
      ),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  final UserSummary user;
  const _ProfileHeader({required this.user});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(user.name.isNotEmpty ? user.name : 'Signed in',
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 2),
        Text(user.email, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class _MenuRow extends StatelessWidget {
  final IconData icon;
  final String label;
  const _MenuRow({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 20, color: AppColors.inkMuted),
        const SizedBox(width: 12),
        Text(label),
      ],
    );
  }
}

String _initials(String source) {
  final parts = source.trim().split(RegExp(r'\s+'));
  if (parts.isEmpty || parts.first.isEmpty) return '?';
  if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
  return (parts.first.substring(0, 1) + parts.last.substring(0, 1))
      .toUpperCase();
}

/// Search input bound to [restaurantQueryProvider]; reusable by the navbar
/// and the home hero. Keeps its text in sync when another field changes it.
class RestaurantSearchField extends ConsumerStatefulWidget {
  final String hint;
  final ValueChanged<String>? onSubmitted;
  final FocusNode? focusNode;

  const RestaurantSearchField({
    super.key,
    this.hint = 'Search restaurants or cuisines',
    this.onSubmitted,
    this.focusNode,
  });

  @override
  ConsumerState<RestaurantSearchField> createState() =>
      _RestaurantSearchFieldState();
}

class _RestaurantSearchFieldState extends ConsumerState<RestaurantSearchField> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller =
        TextEditingController(text: ref.read(restaurantQueryProvider));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<String>(restaurantQueryProvider, (previous, next) {
      if (next != _controller.text) _controller.text = next;
    });
    return TextField(
      controller: _controller,
      focusNode: widget.focusNode,
      textInputAction: TextInputAction.search,
      onChanged: (value) =>
          ref.read(restaurantQueryProvider.notifier).state = value,
      onSubmitted: widget.onSubmitted,
      decoration: InputDecoration(
        isDense: true,
        hintText: widget.hint,
        prefixIcon: const Icon(Icons.search_rounded, size: 20),
        suffixIcon: _controller.text.isEmpty
            ? null
            : IconButton(
                icon: const Icon(Icons.close_rounded, size: 18),
                tooltip: 'Clear search',
                onPressed: () {
                  _controller.clear();
                  ref.read(restaurantQueryProvider.notifier).state = '';
                },
              ),
        fillColor: AppColors.field,
        border: OutlineInputBorder(
          borderRadius: AppRadius.brPill,
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: AppRadius.brPill,
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: AppRadius.brPill,
          borderSide: const BorderSide(color: AppColors.primary, width: 1.6),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
    );
  }
}

/// Compact navigation for narrow screens, opened from the navbar hamburger.
class NavDrawer extends ConsumerWidget {
  const NavDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    final count = ref.watch(cartProvider).totalQuantity;
    return Drawer(
      child: SafeArea(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            Padding(
              padding: const EdgeInsets.all(AppSpace.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const BrandMark(size: 36, textColor: AppColors.primary),
                  if (session != null) ...[
                    const SizedBox(height: AppSpace.md),
                    Text(session.name.isNotEmpty ? session.name : session.email,
                        style: Theme.of(context).textTheme.titleSmall),
                    Text(session.email,
                        style: Theme.of(context).textTheme.bodySmall),
                  ],
                ],
              ),
            ),
            const Divider(height: 1),
            _DrawerTile(
              icon: Icons.storefront_rounded,
              label: 'Restaurants',
              onTap: () {
                Navigator.of(context).pop();
                goHome(context, ref);
              },
            ),
            _DrawerTile(
              icon: Icons.shopping_bag_outlined,
              label: 'Cart',
              trailing: count > 0 ? Badge(label: Text('$count')) : null,
              onTap: () {
                Navigator.of(context).pop();
                pushOnce(context, '/cart');
              },
            ),
            _DrawerTile(
              icon: Icons.receipt_long_rounded,
              label: 'My Orders',
              onTap: () {
                Navigator.of(context).pop();
                if (session == null) {
                  pushOnce(context, '/signin');
                } else {
                  pushOnce(context, '/history');
                }
              },
            ),
            if (session != null) ...[
              _DrawerTile(
                icon: Icons.account_circle_outlined,
                label: 'Profile Details',
                onTap: () {
                  Navigator.of(context).pop();
                  pushOnce(context, '/profile');
                },
              ),
              if (session.role == 'admin')
                _DrawerTile(
                  icon: Icons.admin_panel_settings_outlined,
                  label: 'Admin overview',
                  onTap: () {
                    Navigator.of(context).pop();
                    pushOnce(context, '/admin');
                  },
                ),
              const Divider(height: 1),
              _DrawerTile(
                icon: Icons.logout_rounded,
                label: 'Logout',
                onTap: () {
                  Navigator.of(context).pop();
                  ref.read(cartProvider.notifier).clear();
                  final future = ref.read(sessionProvider.notifier).signOut();
                  Navigator.of(context)
                      .pushNamedAndRemoveUntil('/signin', (_) => false);
                  future.ignore();
                },
              ),
            ] else ...[
              const Divider(height: 1),
              _DrawerTile(
                icon: Icons.login_rounded,
                label: 'Log in',
                onTap: () {
                  Navigator.of(context).pop();
                  pushOnce(context, '/signin');
                },
              ),
              _DrawerTile(
                icon: Icons.person_add_alt_1_rounded,
                label: 'Register',
                onTap: () {
                  Navigator.of(context).pop();
                  pushOnce(context, '/register');
                },
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _DrawerTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final Widget? trailing;
  final VoidCallback onTap;

  const _DrawerTile(
      {required this.icon,
      required this.label,
      this.trailing,
      required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon),
      title: Text(label,
          style: Theme.of(context)
              .textTheme
              .titleSmall
              ?.copyWith(fontWeight: FontWeight.w600)),
      trailing: trailing,
      onTap: onTap,
    );
  }
}

/// Shared focus node so the navbar search icon can focus the home search bar.
final restaurantSearchFocusProvider = Provider<FocusNode>((ref) {
  final node = FocusNode(debugLabel: 'restaurantSearch');
  ref.onDispose(node.dispose);
  return node;
});
