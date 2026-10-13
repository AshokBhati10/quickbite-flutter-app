// Shared responsive scaffold + state widgets.
import 'package:flutter/material.dart';

/// Phone (<700px) vs desktop layout without overflow.
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
    final content = width > 700
        ? Center(child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 900), child: body))
        : body;
    return Scaffold(
      appBar: AppBar(title: Text(title), actions: actions),
      body: SafeArea(child: content),
      floatingActionButton: floatingActionButton,
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
  const EmptyView({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Semantics(
        label: 'Empty: $message',
        child: Text(message, textAlign: TextAlign.center),
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
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Semantics(label: 'Error: $message', child: Text(message)),
          if (onRetry != null)
            TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
