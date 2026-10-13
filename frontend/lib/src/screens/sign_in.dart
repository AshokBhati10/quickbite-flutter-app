// Sign-in with loading / invalid-credential / network-error states.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../widgets/app_scaffold.dart';

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
    return ResponsiveScaffold(
      title: 'QuickBite sign in',
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            key: const Key('email'),
            controller: _email,
            decoration: const InputDecoration(labelText: 'Email'),
            keyboardType: TextInputType.emailAddress,
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('password'),
            controller: _password,
            decoration: const InputDecoration(labelText: 'Password'),
            obscureText: true,
            onSubmitted: (_) => _signIn(),
          ),
          const SizedBox(height: 16),
          if (_error != null)
            Semantics(
              label: 'Sign-in error',
              child: Text(_error!,
                  key: const Key('error'),
                  style: const TextStyle(color: Colors.red)),
            ),
          const SizedBox(height: 8),
          _loading
              ? const LoadingView()
              : ElevatedButton(
                  key: const Key('signIn'),
                  onPressed: _signIn,
                  child: const Text('Sign in'),
                ),
        ],
      ),
    );
  }
}
