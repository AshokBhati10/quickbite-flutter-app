// Shared visual components used across screens so the same card, pill,
// heading and stepper styling appears everywhere (design-system layer).
import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// QuickBite wordmark: a rounded gradient tile with a utensil glyph plus,
/// optionally, the wordmark. Used by the navbar and the auth screens.
class BrandMark extends StatelessWidget {
  final double size;
  final bool showText;
  final VoidCallback? onTap;
  final Color textColor;

  const BrandMark({
    super.key,
    this.size = 40,
    this.showText = true,
    this.onTap,
    this.textColor = AppColors.ink,
  });

  @override
  Widget build(BuildContext context) {
    final logo = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.primary, Color(0xFFFF7A45)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(size * 0.32),
        boxShadow: AppShadows.soft,
      ),
      child: Icon(Icons.restaurant_rounded,
          color: Colors.white, size: size * 0.55),
    );

    final content = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        logo,
        if (showText) ...[
          const SizedBox(width: 10),
          Text(
            'QuickBite',
            style: TextStyle(
              fontFamily: AppTheme.fontFamily,
              fontSize: size * 0.5,
              fontWeight: FontWeight.w700,
              color: textColor,
              letterSpacing: -0.3,
            ),
          ),
        ],
      ],
    );

    if (onTap == null) return content;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.md),
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: content,
      ),
    );
  }
}

/// Section heading with an optional supporting line and trailing action.
class SectionHeading extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final EdgeInsetsGeometry padding;

  const SectionHeading({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
    this.padding = EdgeInsets.zero,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: padding,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: theme.textTheme.titleLarge),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(subtitle!, style: theme.textTheme.bodySmall),
                ],
              ],
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

/// Small rounded information pill (icon + optional label) on a tinted surface.
class InfoPill extends StatelessWidget {
  final IconData icon;
  final String? label;
  final Color color;
  final double iconSize;

  const InfoPill({
    super.key,
    required this.icon,
    this.label,
    this.color = AppColors.primary,
    this.iconSize = 16,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: AppRadius.brPill,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: iconSize, color: color),
          if (label != null) ...[
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                label!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: color,
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Colour-coded order status chip used by order history, tracking and admin.
class StatusPill extends StatelessWidget {
  final String status;
  final String? label;
  final bool dense;

  const StatusPill({super.key, required this.status, this.label, this.dense = false});

  static (Color fg, Color bg) palette(String status) {
    if (status == 'FAILED' || status == 'PAYMENT_FAILED') {
      return (AppColors.error, AppColors.errorSoft);
    }
    if (status == 'DRIVER_ASSIGNED' || status == 'PAID') {
      return (AppColors.green, AppColors.greenSoft);
    }
    if (status == 'CONFIRMED') {
      return (AppColors.greenDark, AppColors.greenSoft);
    }
    if (status == 'PENDING') {
      return (AppColors.amber, AppColors.amberSoft);
    }
    return (AppColors.primary, AppColors.primarySoft);
  }

  @override
  Widget build(BuildContext context) {
    final (fg, bg) = palette(status);
    return Container(
      padding: EdgeInsets.symmetric(
          horizontal: dense ? 8 : 10, vertical: dense ? 3 : 5),
      decoration: BoxDecoration(color: bg, borderRadius: AppRadius.brPill),
      child: Text(
        (label ?? status.replaceAll('_', ' ')),
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: fg,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.2,
            ),
      ),
    );
  }
}

/// Pill-shaped icon + text action, used for "Add" affordances on menus.
class PillIconButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? tooltip;
  final VoidCallback? onPressed;

  const PillIconButton({
    super.key,
    required this.icon,
    required this.label,
    this.tooltip,
    this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    final button = Material(
      color: enabled ? AppColors.primary : AppColors.borderSoft,
      borderRadius: AppRadius.brPill,
      child: InkWell(
        onTap: onPressed,
        borderRadius: AppRadius.brPill,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon,
                  size: 16,
                  color: enabled ? Colors.white : AppColors.inkMuted),
              const SizedBox(width: 6),
              Text(
                label,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: enabled ? Colors.white : AppColors.inkMuted,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
    if (tooltip == null) return button;
    return Tooltip(message: tooltip!, child: button);
  }
}

/// Quantity stepper for cart lines.
class QuantityStepper extends StatelessWidget {
  final int quantity;
  final VoidCallback onDecrement;
  final VoidCallback onIncrement;

  const QuantityStepper({
    super.key,
    required this.quantity,
    required this.onDecrement,
    required this.onIncrement,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.field,
        borderRadius: AppRadius.brPill,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _StepButton(
            icon: Icons.remove_rounded,
            tooltip: 'Decrease quantity',
            onPressed: onDecrement,
          ),
          ConstrainedBox(
            constraints: const BoxConstraints(minWidth: 28),
            child: Text(
              '$quantity',
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          _StepButton(
            icon: Icons.add_rounded,
            tooltip: 'Increase quantity',
            onPressed: onIncrement,
          ),
        ],
      ),
    );
  }
}

class _StepButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  const _StepButton(
      {required this.icon, required this.tooltip, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      icon: Icon(icon, size: 18),
      tooltip: tooltip,
      onPressed: onPressed,
      visualDensity: VisualDensity.compact,
      style: IconButton.styleFrom(
        foregroundColor: AppColors.primary,
        minimumSize: const Size(34, 34),
        padding: EdgeInsets.zero,
      ),
    );
  }
}

/// Standalone auth layout: a warm gradient backdrop with the form card
/// centred on phones and paired with a branded panel on wide/desktop screens.
/// Contains no navigation chrome, by design.
class AuthShell extends StatelessWidget {
  final Widget form;
  const AuthShell({super.key, required this.form});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [AppColors.background, AppColors.primarySoft],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
      ),
      child: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 1000;
            final card = ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: form,
            );
            if (!wide) {
              return Center(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(AppSpace.xxl),
                  child: card,
                ),
              );
            }
            return Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(AppSpace.xxxl),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1040),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      const Expanded(child: _BrandPanel()),
                      const SizedBox(width: AppSpace.xxxl),
                      card,
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _BrandPanel extends StatelessWidget {
  const _BrandPanel();

  @override
  Widget build(BuildContext context) {
    return WarmPanel(
      gradient: const [AppColors.primary, Color(0xFFFF7A45)],
      borderRadius: AppRadius.brXl,
      padding: const EdgeInsets.all(AppSpace.xxxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.18),
              borderRadius: AppRadius.brLg,
            ),
            child: const Icon(Icons.restaurant_rounded,
                color: Colors.white, size: 32),
          ),
          const SizedBox(height: AppSpace.xxl),
          Text(
            'Food from every\nkitchen you love',
            style: Theme.of(context).textTheme.displaySmall?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                  height: 1.15,
                ),
          ),
          const SizedBox(height: AppSpace.md),
          Text(
            'One account, one cart, every restaurant in the marketplace.',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: Colors.white.withValues(alpha: 0.92),
                ),
          ),
          const SizedBox(height: AppSpace.xxl),
          const _BrandBullet(icon: Icons.storefront_rounded, text: 'Order across multiple restaurants'),
          const SizedBox(height: AppSpace.md),
          const _BrandBullet(icon: Icons.shopping_bag_outlined, text: 'One cart, live item count'),
          const SizedBox(height: AppSpace.md),
          const _BrandBullet(icon: Icons.delivery_dining_rounded, text: 'Track every order end to end'),
        ],
      ),
    );
  }
}

class _BrandBullet extends StatelessWidget {
  final IconData icon;
  final String text;
  const _BrandBullet({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 30,
          height: 30,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.18),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, size: 16, color: Colors.white),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            text,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
          ),
        ),
      ],
    );
  }
}

/// A warm content panel used for hero sections and summaries.
class WarmPanel extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final BorderRadius? borderRadius;
  final List<Color>? gradient;

  const WarmPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpace.xl),
    this.borderRadius,
    this.gradient,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: gradient == null ? AppColors.surfaceWarm : null,
        gradient: gradient == null
            ? null
            : LinearGradient(
                colors: gradient!,
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
        borderRadius: borderRadius ?? AppRadius.brXl,
        border: gradient == null
            ? Border.all(color: AppColors.borderSoft)
            : null,
      ),
      child: child,
    );
  }
}
