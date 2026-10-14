// Shared responsive scaffolds + state widgets, styled by the design system.
import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'app_navbar.dart';

/// Sub-page layout: a light branded bar with a back affordance and a centred,
/// max-width content column so desktop screens do not stretch awkwardly.
class ResponsiveScaffold extends StatelessWidget {
  final String title;
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;

  const ResponsiveScaffold(
      {super.key,
      required this.title,
      required this.body,
      this.actions,
      this.floatingActionButton});

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    final content = width > 720
        ? Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 980),
              child: body,
            ),
          )
        : body;
    return Scaffold(
      appBar: AppBar(title: Text(title), actions: actions),
      body: SafeArea(child: content),
      floatingActionButton: floatingActionButton,
    );
  }
}

/// Primary screens: full-width navbar plus a compact drawer on narrow screens.
class NavScaffold extends StatelessWidget {
  final Widget body;
  final Widget? floatingActionButton;

  const NavScaffold({super.key, required this.body, this.floatingActionButton});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const AppNavBar(),
      drawer: const NavDrawer(),
      body: SafeArea(child: body),
      floatingActionButton: floatingActionButton,
    );
  }
}

/// Centred max-width wrapper for scrollable page content on wide screens.
class ContentWidth extends StatelessWidget {
  final Widget child;
  final double maxWidth;
  final EdgeInsetsGeometry padding;

  const ContentWidth({
    super.key,
    required this.child,
    this.maxWidth = 1180,
    this.padding = const EdgeInsets.all(AppSpace.lg),
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: Padding(padding: padding, child: child),
      ),
    );
  }
}

class LoadingView extends StatelessWidget {
  const LoadingView({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Semantics(
        label: 'Loading',
        child: const CircularProgressIndicator(),
      ),
    );
  }
}

class EmptyView extends StatelessWidget {
  final String message;
  final IconData icon;

  const EmptyView(
      {super.key, required this.message, this.icon = Icons.inbox_outlined});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.xxl),
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
              child: Icon(icon, size: 30, color: AppColors.inkMuted),
            ),
            const SizedBox(height: AppSpace.lg),
            Semantics(
              label: 'Empty: $message',
              child: Text(
                message,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;

  const ErrorView({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: const BoxDecoration(
                color: AppColors.errorSoft,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.wifi_off_rounded,
                  size: 28, color: AppColors.error),
            ),
            const SizedBox(height: AppSpace.lg),
            Semantics(
              label: 'Error: $message',
              child: Text(message, textAlign: TextAlign.center),
            ),
            if (onRetry != null) ...[
              const SizedBox(height: AppSpace.md),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Retry'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
