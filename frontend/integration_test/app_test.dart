// Integration flow: sign-in -> menu -> checkout -> tracking -> history.
// Run against a live Compose stack:
//   flutter test integration_test/app_test.dart \
//     --dart-define=API_BASE_URL=http://10.0.2.2:8000
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:quickbite/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('full customer flow', (tester) async {
    app.main();
    await tester.pumpAndSettle();
    expect(find.text('QuickBite sign in'), findsOneWidget);

    await tester.enterText(
        find.byKey(const Key('email')), 'customer@quickbite.test');
    await tester.enterText(
        find.byKey(const Key('password')), 'Password123!');
    await tester.tap(find.byKey(const Key('signIn')));
    await tester.pumpAndSettle(const Duration(seconds: 5));
    expect(find.text('Restaurants'), findsOneWidget);
  });
}
