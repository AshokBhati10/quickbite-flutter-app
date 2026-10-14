// Typed request/response models mirroring the /api/v1 contract.
// Money is integer minor units with a currency code.

class UserSummary {
  final String id;
  final String email;
  final String role;
  final String name;

  const UserSummary(
      {required this.id,
      required this.email,
      required this.role,
      required this.name});

  factory UserSummary.fromJson(Map<String, dynamic> json) => UserSummary(
        id: json['id'] as String,
        email: json['email'] as String,
        role: json['role'] as String,
        name: (json['name'] ?? '') as String,
      );
}

class Restaurant {
  final String id;
  final String name;
  final String description;
  final String cuisine;
  final String imageUrl;
  final bool isActive;

  const Restaurant(
      {required this.id,
      required this.name,
      required this.description,
      this.cuisine = '',
      this.imageUrl = '',
      required this.isActive});

  factory Restaurant.fromJson(Map<String, dynamic> json) => Restaurant(
        id: json['id'] as String,
        name: json['name'] as String,
        description: (json['description'] ?? '') as String,
        cuisine: (json['cuisine'] ?? '') as String,
        imageUrl: (json['image_url'] ?? '') as String,
        isActive: (json['is_active'] ?? true) as bool,
      );
}

class MenuItem {
  final String id;
  final String restaurantId;
  final String name;
  final String description;
  final String category;
  final String imageUrl;
  final int priceMinor;
  final String currency;
  final bool isActive;

  const MenuItem(
      {required this.id,
      required this.restaurantId,
      required this.name,
      this.description = '',
      this.category = '',
      this.imageUrl = '',
      required this.priceMinor,
      required this.currency,
      required this.isActive});

  factory MenuItem.fromJson(Map<String, dynamic> json) => MenuItem(
        id: json['id'] as String,
        restaurantId: json['restaurant_id'] as String,
        name: json['name'] as String,
        description: (json['description'] ?? '') as String,
        category: (json['category'] ?? '') as String,
        imageUrl: (json['image_url'] ?? '') as String,
        priceMinor: json['price_minor'] as int,
        currency: (json['currency'] ?? 'INR') as String,
        isActive: (json['is_active'] ?? true) as bool,
      );
}

String formatMinor(int amountMinor, String currency) {
  return '$currency ${(amountMinor / 100).toStringAsFixed(2)}';
}

class CartLine {
  final MenuItem item;
  int quantity;

  CartLine({required this.item, required this.quantity});

  int get lineTotal => item.priceMinor * quantity;
}

class Cart {
  String? restaurantId;
  final Map<String, CartLine> lines = {};

  bool get isEmpty => lines.isEmpty;
  int get distinctCount => lines.length;
  int get totalQuantity =>
      lines.values.fold(0, (sum, line) => sum + line.quantity);
  int get subtotal => lines.values.fold(0, (sum, line) => sum + line.lineTotal);

  /// Single-restaurant rule: adding from another restaurant clears the cart.
  void add(MenuItem item, int quantity) {
    if (restaurantId != null && restaurantId != item.restaurantId) {
      lines.clear();
    }
    restaurantId = item.restaurantId;
    final existing = lines[item.id];
    if (existing == null) {
      lines[item.id] = CartLine(item: item, quantity: quantity);
    } else {
      existing.quantity = (existing.quantity + quantity).clamp(1, 20);
    }
  }

  void remove(String menuItemId) {
    lines.remove(menuItemId);
    if (lines.isEmpty) restaurantId = null;
  }

  void changeQuantity(String menuItemId, int delta) {
    final existing = lines[menuItemId];
    if (existing == null) return;
    final next = existing.quantity + delta;
    if (next < 1) {
      remove(menuItemId);
    } else {
      existing.quantity = next.clamp(1, 20);
    }
  }

  Map<String, dynamic> toCheckoutJson(String address) => {
        'restaurant_id': restaurantId,
        'delivery_address': address,
        'items': lines.values
            .map((l) => {'menu_item_id': l.item.id, 'quantity': l.quantity})
            .toList(),
      };
}

class OrderLine {
  final String name;
  final int quantity;
  final int unitPriceMinor;

  const OrderLine(
      {required this.name,
      required this.quantity,
      required this.unitPriceMinor});

  factory OrderLine.fromJson(Map<String, dynamic> json) => OrderLine(
        name: (json['name'] ?? '') as String,
        quantity: (json['quantity'] ?? 0) as int,
        unitPriceMinor: (json['unit_price_minor'] ?? 0) as int,
      );
}

class OrderSummary {
  final String id;
  final String status;
  final int totalMinor;
  final String currency;
  final int version;
  final String restaurantName;
  final DateTime? createdAt;
  final List<OrderLine> lines;
  final String? failureCode;

  const OrderSummary(
      {required this.id,
      required this.status,
      required this.totalMinor,
      required this.currency,
      required this.version,
      this.restaurantName = '',
      this.createdAt,
      this.lines = const [],
      this.failureCode});

  factory OrderSummary.fromJson(Map<String, dynamic> json) => OrderSummary(
        id: json['id'] as String,
        status: json['status'] as String,
        totalMinor: (json['total_minor'] ?? json['total_amount_minor'] ?? 0) as int,
        currency: (json['currency'] ?? 'INR') as String,
        version: (json['version'] ?? 1) as int,
        restaurantName: (json['restaurant_name'] ?? '') as String,
        createdAt: DateTime.tryParse((json['created_at'] ?? '') as String),
        lines: ((json['items'] ?? []) as List)
            .map((e) => OrderLine.fromJson(e as Map<String, dynamic>))
            .toList(),
        failureCode: json['failure_code'] as String?,
      );
}

bool isTerminalStatus(String status) =>
    status == 'DRIVER_ASSIGNED' || status == 'PAYMENT_FAILED' || status == 'FAILED';

String failureExplanation(String? failureCode, String status) {
  if (status == 'PAYMENT_FAILED' || failureCode == 'payment_failed') {
    return 'Payment could not be completed. No further charge will be attempted for this order; please place a new order.';
  }
  if (status == 'FAILED') {
    if (failureCode == 'restaurant_declined') {
      return 'The restaurant could not accept this order.';
    }
    if (failureCode == 'delivery_failed') {
      return 'No driver could be assigned to this order.';
    }
    return 'This order could not be completed.';
  }
  return '';
}
