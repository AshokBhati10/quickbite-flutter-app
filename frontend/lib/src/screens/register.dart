// Account registration, then straight into the authenticated session.
// Standalone (no global navbar), styled by the shared design system.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/app_scaffold.dart';
import '../widgets/ui.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _register() async {
    final name = _name.text.trim();
    final email = _email.text.trim();
    final password = _password.text;
    if (name.isEmpty) {
      setState(() => _error = 'Enter your name.');
      return;
    }
    if (!email.contains('@')) {
      setState(() => _error = 'Enter a valid email address.');
      return;
    }
    if (password.length < 8) {
      setState(() => _error = 'Password must be at least 8 characters.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final body =
          await ref.read(apiClientProvider).register(email, password, name);
      final user = UserSummary.fromJson(body['user'] as Map<String, dynamic>);
      ref.read(sessionProvider.notifier).signIn(user);
      if (!mounted) return;
      Navigator.of(context)
          .pushNamedAndRemoveUntil('/restaurants', (_) => false);
    } on ApiException catch (err) {
      if (!mounted) return;
      setState(() {
        _error = err.message;
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AuthShell(
      form: Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Center(child: BrandMark(size: 44, textColor: AppColors.primary)),
              const SizedBox(height: AppSpace.xl),
              Text('Join QuickBite',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.headlineSmall),
              const SizedBox(height: 6),
              Text(
                'Create an account to start ordering.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: AppColors.inkMuted),
              ),
              const SizedBox(height: AppSpace.xxl),
              TextField(
                key: const Key('registerName'),
                controller: _name,
                decoration: const InputDecoration(
                  labelText: 'Full name',
                  prefixIcon: Icon(Icons.person_outline_rounded),
                ),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: AppSpace.md),
              TextField(
                key: const Key('registerEmail'),
                controller: _email,
                decoration: const InputDecoration(
                  labelText: 'Email',
                  prefixIcon: Icon(Icons.mail_outline_rounded),
                ),
                keyboardType: TextInputType.emailAddress,
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: AppSpace.md),
              TextField(
                key: const Key('registerPassword'),
                controller: _password,
                decoration: const InputDecoration(
                  labelText: 'Password',
                  helperText: 'At least 8 characters',
                  prefixIcon: Icon(Icons.lock_outline_rounded),
                ),
                obscureText: true,
                onSubmitted: (_) => _register(),
              ),
              const SizedBox(height: AppSpace.lg),
              if (_error != null) ...[
                Semantics(
                  label: 'Registration error',
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: AppColors.errorSoft,
                      borderRadius: AppRadius.brSm,
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline_rounded,
                            size: 18, color: AppColors.error),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _error!,
                            key: const Key('registerError'),
                            style: theme.textTheme.bodySmall
                                ?.copyWith(color: AppColors.error),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: AppSpace.lg),
              ],
              _loading
                  ? const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: LoadingView(),
                    )
                  : FilledButton(
                      key: const Key('register'),
                      onPressed: _register,
                      child: const Text('Create account'),
                    ),
              const SizedBox(height: AppSpace.sm),
              TextButton(
                onPressed: _loading
                    ? null
                    : () => Navigator.of(context).maybePop(),
                child: const Text('Back to sign in'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
