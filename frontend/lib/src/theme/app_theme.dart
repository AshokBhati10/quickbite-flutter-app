// QuickBite design system: single source of truth for colour, type, spacing,
// radii, elevation and component styling. Inspired by a warm, friendly,
// rounded food-delivery visual language (cream backgrounds, coral accent,
// soft cards, pill controls) — adapted, not copied, and applied on every screen.
import 'package:flutter/material.dart';

/// Brand + semantic colour tokens.
abstract final class AppColors {
  // Brand
  static const Color primary = Color(0xFFFF5A2C); // warm coral-orange
  static const Color primaryDark = Color(0xFF8C2F14);
  static const Color primarySoft = Color(0xFFFFE1D6); // peach container

  // Accents
  static const Color green = Color(0xFF12A05C);
  static const Color greenDark = Color(0xFF0B6B3E);
  static const Color greenSoft = Color(0xFFDDF3E7);
  static const Color amber = Color(0xFFF5A623);
  static const Color amberSoft = Color(0xFFFFF1D6);

  // Feedback
  static const Color error = Color(0xFFD64545);
  static const Color errorSoft = Color(0xFFFBE0E0);

  // Surfaces
  static const Color background = Color(0xFFFFF8F3); // warm cream
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceWarm = Color(0xFFFBF3ED);
  static const Color field = Color(0xFFF6EEE8); // input / chip fill

  // Text
  static const Color ink = Color(0xFF231A15); // high emphasis
  static const Color inkMuted = Color(0xFF8B7A70); // medium emphasis

  // Lines
  static const Color border = Color(0xFFEFE0D6);
  static const Color borderSoft = Color(0xFFF4E9E1);
}

/// Corner radii.
abstract final class AppRadius {
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 20;
  static const double xl = 28;
  static const double pill = 999;

  static BorderRadius get brSm => BorderRadius.circular(sm);
  static BorderRadius get brMd => BorderRadius.circular(md);
  static BorderRadius get brLg => BorderRadius.circular(lg);
  static BorderRadius get brXl => BorderRadius.circular(xl);
  static BorderRadius get brPill => BorderRadius.circular(pill);
}

/// Spacing scale (multiples of four).
abstract final class AppSpace {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double xxxl = 32;
}

/// Soft, low-contrast elevation used by cards and floating surfaces.
abstract final class AppShadows {
  static const List<BoxShadow> card = [
    BoxShadow(
      color: Color(0x14120A05),
      blurRadius: 24,
      offset: Offset(0, 10),
      spreadRadius: -8,
    ),
  ];
  static const List<BoxShadow> soft = [
    BoxShadow(
      color: Color(0x0F000000),
      blurRadius: 18,
      offset: Offset(0, 8),
      spreadRadius: -6,
    ),
  ];
}

/// Builds the app-wide [ThemeData].
abstract final class AppTheme {
  static const String fontFamily = 'Quicksand';

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      brightness: Brightness.light,
    ).copyWith(
      primary: AppColors.primary,
      onPrimary: Colors.white,
      primaryContainer: AppColors.primarySoft,
      onPrimaryContainer: AppColors.primaryDark,
      secondary: AppColors.green,
      onSecondary: Colors.white,
      secondaryContainer: AppColors.greenSoft,
      onSecondaryContainer: AppColors.greenDark,
      tertiary: AppColors.amber,
      onTertiary: Colors.white,
      tertiaryContainer: AppColors.amberSoft,
      onTertiaryContainer: Colors.black87,
      error: AppColors.error,
      onError: Colors.white,
      errorContainer: AppColors.errorSoft,
      onErrorContainer: AppColors.error,
      surface: AppColors.surface,
      onSurface: AppColors.ink,
      onSurfaceVariant: AppColors.inkMuted,
      surfaceContainerLowest: AppColors.surface,
      surfaceContainerLow: AppColors.surfaceWarm,
      surfaceContainer: AppColors.field,
      surfaceContainerHigh: AppColors.field,
      surfaceContainerHighest: AppColors.borderSoft,
      outline: AppColors.border,
      outlineVariant: AppColors.borderSoft,
    );

    final base = ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      fontFamily: fontFamily,
      scaffoldBackgroundColor: AppColors.background,
    );

    return base.copyWith(
      textTheme: _textTheme(base.textTheme),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.ink,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontFamily: fontFamily,
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: AppColors.ink,
        ),
        shape: Border(bottom: BorderSide(color: AppColors.borderSoft)),
        iconTheme: IconThemeData(color: AppColors.ink),
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadius.brLg,
          side: const BorderSide(color: AppColors.borderSoft),
        ),
      ),
      chipTheme: const ChipThemeData(
        backgroundColor: AppColors.field,
        selectedColor: AppColors.primary,
        secondarySelectedColor: AppColors.primary,
        disabledColor: AppColors.borderSoft,
        side: BorderSide.none,
        shape: StadiumBorder(),
        showCheckmark: false,
        labelStyle: TextStyle(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w600,
          color: AppColors.inkMuted,
        ),
        secondaryLabelStyle: TextStyle(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
        padding: EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        labelPadding: EdgeInsets.symmetric(horizontal: 2),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.field,
        isDense: true,
        hintStyle: const TextStyle(
          fontFamily: fontFamily,
          color: AppColors.inkMuted,
          fontWeight: FontWeight.w500,
        ),
        labelStyle: const TextStyle(
          fontFamily: fontFamily,
          color: AppColors.inkMuted,
          fontWeight: FontWeight.w600,
        ),
        floatingLabelStyle: const TextStyle(
          fontFamily: fontFamily,
          color: AppColors.primary,
          fontWeight: FontWeight.w700,
        ),
        prefixIconColor: AppColors.inkMuted,
        suffixIconColor: AppColors.inkMuted,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: const BorderSide(color: AppColors.primary, width: 1.6),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: const BorderSide(color: AppColors.error),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: const BorderSide(color: AppColors.error, width: 1.6),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          disabledBackgroundColor: AppColors.borderSoft,
          disabledForegroundColor: AppColors.inkMuted,
          elevation: 0,
          minimumSize: const Size(0, 48),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          shape: const StadiumBorder(),
          textStyle: const TextStyle(
            fontFamily: fontFamily,
            fontWeight: FontWeight.w700,
            fontSize: 15,
          ),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          disabledBackgroundColor: AppColors.borderSoft,
          disabledForegroundColor: AppColors.inkMuted,
          elevation: 0,
          minimumSize: const Size(0, 48),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          shape: const StadiumBorder(),
          textStyle: const TextStyle(
            fontFamily: fontFamily,
            fontWeight: FontWeight.w700,
            fontSize: 15,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.primary,
          side: const BorderSide(color: AppColors.border),
          minimumSize: const Size(0, 46),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
          shape: const StadiumBorder(),
          textStyle: const TextStyle(
            fontFamily: fontFamily,
            fontWeight: FontWeight.w700,
            fontSize: 14,
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.primary,
          shape: const StadiumBorder(),
          textStyle: const TextStyle(
            fontFamily: fontFamily,
            fontWeight: FontWeight.w700,
            fontSize: 14,
          ),
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(foregroundColor: AppColors.ink),
      ),
      dividerTheme: const DividerThemeData(
        color: AppColors.borderSoft,
        thickness: 1,
        space: 1,
      ),
      listTileTheme: const ListTileThemeData(
        iconColor: AppColors.inkMuted,
        textColor: AppColors.ink,
        contentPadding: EdgeInsets.symmetric(horizontal: 16),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: AppColors.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 6,
        shadowColor: const Color(0x22000000),
        shape: RoundedRectangleBorder(borderRadius: AppRadius.brMd),
        textStyle: const TextStyle(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w600,
          color: AppColors.ink,
        ),
      ),
      drawerTheme: const DrawerThemeData(
        backgroundColor: AppColors.surface,
        surfaceTintColor: Colors.transparent,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.ink,
        contentTextStyle: const TextStyle(
          fontFamily: fontFamily,
          color: Colors.white,
          fontWeight: FontWeight.w600,
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: AppRadius.brMd),
      ),
      badgeTheme: const BadgeThemeData(
        backgroundColor: AppColors.primary,
        textColor: Colors.white,
        textStyle: TextStyle(
          fontFamily: fontFamily,
          fontWeight: FontWeight.w700,
          fontSize: 11,
        ),
      ),
      progressIndicatorTheme:
          const ProgressIndicatorThemeData(color: AppColors.primary),
      splashColor: AppColors.primary.withValues(alpha: 0.08),
      highlightColor: AppColors.primary.withValues(alpha: 0.05),
    );
  }

  static TextTheme _textTheme(TextTheme base) {
    return base
        .copyWith(
          displaySmall: base.displaySmall?.copyWith(
              fontSize: 34, fontWeight: FontWeight.w700, height: 1.15),
          headlineMedium: base.headlineMedium?.copyWith(
              fontSize: 28, fontWeight: FontWeight.w700, height: 1.2),
          headlineSmall: base.headlineSmall?.copyWith(
              fontSize: 24, fontWeight: FontWeight.w700, height: 1.2),
          titleLarge: base.titleLarge?.copyWith(
              fontSize: 20, fontWeight: FontWeight.w700, height: 1.25),
          titleMedium: base.titleMedium?.copyWith(
              fontSize: 16, fontWeight: FontWeight.w700, height: 1.3),
          titleSmall: base.titleSmall?.copyWith(
              fontSize: 14, fontWeight: FontWeight.w600, height: 1.3),
          bodyLarge: base.bodyLarge?.copyWith(
              fontSize: 16, fontWeight: FontWeight.w500, height: 1.45),
          bodyMedium: base.bodyMedium?.copyWith(
              fontSize: 14, fontWeight: FontWeight.w500, height: 1.45),
          bodySmall: base.bodySmall?.copyWith(
              fontSize: 12.5,
              fontWeight: FontWeight.w500,
              height: 1.4,
              color: AppColors.inkMuted),
          labelLarge: base.labelLarge?.copyWith(
              fontSize: 14, fontWeight: FontWeight.w700),
          labelMedium: base.labelMedium?.copyWith(
              fontSize: 12, fontWeight: FontWeight.w700),
          labelSmall: base.labelSmall?.copyWith(
              fontSize: 11, fontWeight: FontWeight.w700),
        )
        .apply(
          fontFamily: fontFamily,
          bodyColor: AppColors.ink,
          displayColor: AppColors.ink,
        );
  }
}
