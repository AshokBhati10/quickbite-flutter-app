// Sign-in with loading / invalid-credential / network-error states.
// Standalone (no global navbar), styled by the shared design system.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/app_scaffold.dart';
import '../widgets/ui.dart';

class SignInScreen extends ConsumerStatefulWidget {
  const SignInScreen({super.key});

  @override
  ConsumerState<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends ConsumerState<SignInScreen> {
  final _email = TextEditingController(text: 'customer@quickbite.test');
  final _password = TextEditingController(text: 'Password123!');
  bool _loading = false;
  String? _error;

  Future<void> _signIn() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = ref.read(apiClientProvider);
      final body = await api.login(_email.text.trim(), _password.text);
      final user = UserSummary.fromJson(body['user'] as Map<String, dynamic>);
      ref.read(sessionProvider.notifier).signIn(user);
      if (!mounted) return;
      Navigator.of(context)
          .pushNamedAndRemoveUntil('/restaurants', (_) => false);
    } on ApiException catch (err) {
      setState(() {
        _error = err.status == 401
            ? 'Invalid email or password.'
            : 'Network error. Check the API address and retry.';
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
              Text(
                'QuickBite sign in',
                textAlign: TextAlign.center,
                style: theme.textTheme.headlineSmall,
              ),
              const SizedBox(height: 6),
              Text(
                'Welcome back — let’s get you ordering.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: AppColors.inkMuted),
              ),
              const SizedBox(height: AppSpace.xxl),
              TextField(
                key: const Key('email'),
                controller: _email,
                decoration: const InputDecoration(
                  labelText: 'Email',
                  prefixIcon: Icon(Icons.mail_outline_rounded),
                ),
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: AppSpace.md),
              TextField(
                key: const Key('password'),
                controller: _password,
                decoration: const InputDecoration(
                  labelText: 'Password',
                  prefixIcon: Icon(Icons.lock_outline_rounded),
                ),
                obscureText: true,
                onSubmitted: (_) => _signIn(),
              ),
              const SizedBox(height: AppSpace.lg),
              if (_error != null) ...[
                Semantics(
                  label: 'Sign-in error',
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
                            key: const Key('error'),
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
                      key: const Key('signIn'),
                      onPressed: _signIn,
                      child: const Text('Sign in'),
                    ),
              const SizedBox(height: AppSpace.sm),
              TextButton(
                key: const Key('toRegister'),
                onPressed: _loading
                    ? null
                    : () => Navigator.of(context).pushNamed('/register'),
                child: const Text('New to QuickBite? Create an account'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
