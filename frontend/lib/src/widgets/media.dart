// Network image with a graceful fallback: a warm themed placeholder while
// loading and a rounded icon block when the URL is missing or fails, so cards
// never break and imagery stays on-brand.
import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class RemoteImage extends StatelessWidget {
  final String url;
  final double? width;
  final double? height;
  final BoxFit fit;
  final double radius;
  final IconData fallbackIcon;

  const RemoteImage({
    super.key,
    required this.url,
    this.width,
    this.height,
    this.fit = BoxFit.cover,
    this.radius = AppRadius.md,
    this.fallbackIcon = Icons.restaurant_rounded,
  });

  @override
  Widget build(BuildContext context) {
    if (url.isEmpty) return _fallback(context);
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: Image.network(
        url,
        width: width,
        height: height,
        fit: fit,
        loadingBuilder: (context, child, progress) {
          if (progress == null) return child;
          return _placeholder(context);
        },
        errorBuilder: (context, error, stackTrace) => _fallback(context),
      ),
    );
  }

  Widget _placeholder(BuildContext context) => Container(
        width: width,
        height: height,
        color: AppColors.surfaceWarm,
        alignment: Alignment.center,
        child: const SizedBox(
          width: 22,
          height: 22,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );

  Widget _fallback(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [AppColors.primarySoft, AppColors.amberSoft],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      alignment: Alignment.center,
      child: Icon(fallbackIcon, size: 32, color: AppColors.primary),
    );
  }
}
