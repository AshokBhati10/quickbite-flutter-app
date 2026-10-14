// Profile details sourced from the authenticated session (/api/v1/me).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/app_scaffold.dart';
import '../widgets/ui.dart';

class ProfileDetailsScreen extends ConsumerStatefulWidget {
  const ProfileDetailsScreen({super.key});

  @override
  ConsumerState<ProfileDetailsScreen> createState() =>
      _ProfileDetailsScreenState();
}

class _ProfileDetailsScreenState extends ConsumerState<ProfileDetailsScreen> {
  UserSummary? _user;
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
      final body = await ref.read(apiClientProvider).getJson('/api/v1/me');
      if (!mounted) return;
      setState(() {
        _user = UserSummary.fromJson(body);
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
    } else {
      final user = _user!;
      content = ContentWidth(
        maxWidth: 640,
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        child: ListView(
          children: [
            _ProfileHeader(user: user),
            const SizedBox(height: AppSpace.lg),
            Card(
              child: Column(
                children: [
                  _DetailRow(
                      icon: Icons.person_outline_rounded,
                      label: 'Name',
                      value: user.name),
                  const Divider(height: 1),
                  _DetailRow(
                      icon: Icons.mail_outline_rounded,
                      label: 'Email',
                      value: user.email),
                  const Divider(height: 1),
                  _DetailRow(
                      icon: Icons.badge_outlined,
                      label: 'Role',
                      value: user.role),
                ],
              ),
            ),
          ],
        ),
      );
    }
    return ResponsiveScaffold(title: 'Profile details', body: content);
  }
}

class _ProfileHeader extends StatelessWidget {
  final UserSummary user;
  const _ProfileHeader({required this.user});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final initial = user.name.isNotEmpty
        ? user.name.substring(0, 1).toUpperCase()
        : '?';
    return WarmPanel(
      gradient: const [AppColors.primary, Color(0xFFFF7A45)],
      padding: const EdgeInsets.all(AppSpace.xl),
      child: Row(
        children: [
          Container(
            width: 72,
            height: 72,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white.withValues(alpha: 0.4)),
            ),
            child: Text(
              initial,
              style: theme.textTheme.headlineSmall
                  ?.copyWith(color: Colors.white, fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(width: AppSpace.lg),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user.name.isNotEmpty ? user.name : 'Signed in',
                  style: theme.textTheme.titleLarge
                      ?.copyWith(color: Colors.white),
                ),
                const SizedBox(height: 4),
                Text(user.email,
                    style: theme.textTheme.bodyMedium?.copyWith(
                        color: Colors.white.withValues(alpha: 0.92))),
                const SizedBox(height: 10),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: AppRadius.brPill,
                  ),
                  child: Text(
                    user.role.toUpperCase(),
                    style: theme.textTheme.labelSmall
                        ?.copyWith(color: Colors.white),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _DetailRow(
      {required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      leading: Container(
        width: 40,
        height: 40,
        alignment: Alignment.center,
        decoration: const BoxDecoration(
          color: AppColors.field,
          shape: BoxShape.circle,
        ),
        child: Icon(icon, size: 20, color: AppColors.primary),
      ),
      title: Text(label, style: theme.textTheme.bodySmall),
      subtitle: Text(
        value.isEmpty ? 'Not provided' : value,
        style: theme.textTheme.titleMedium,
      ),
    );
  }
}
