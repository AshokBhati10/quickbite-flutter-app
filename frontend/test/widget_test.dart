// Widget tests: sign-in states, checkout validation, overflow checks.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:quickbite/src/screens/cart.dart';
import 'package:quickbite/src/screens/sign_in.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('sign-in shows validation area and button',
      (tester) async {
    await tester.pumpWidget(
        const ProviderScope(child: MaterialApp(home: SignInScreen())));
    expect(find.byKey(const Key('email')), findsOneWidget);
    expect(find.byKey(const Key('password')), findsOneWidget);
    expect(find.byKey(const Key('signIn')), findsOneWidget);
  });

  testWidgets('cart validates empty checkout', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(
        const ProviderScope(child: MaterialApp(home: CartScreen())));
    await tester.tap(find.text('Place order'));
    await tester.pump();
    expect(find.text('Add items to your cart before checkout.'), findsOneWidget);
  });

  testWidgets('cart renders phone and desktop sizes without overflow',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    for (final size in [
      const Size(360, 740),
      const Size(1280, 800),
    ]) {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1.0;
      await tester.pumpWidget(ProviderScope(
          child: MaterialApp(
              home: CartScreen(key: Key('cart-${size.width}')))));
      await tester.pump();
      expect(tester.takeException(), isNull);
    }
    tester.view.resetPhysicalSize();
  });

  testWidgets('large text scale does not overflow cart', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const ProviderScope(
        child: MediaQuery(
            data: MediaQueryData(textScaler: TextScaler.linear(2.0)),
            child: MaterialApp(home: CartScreen()))));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
}
