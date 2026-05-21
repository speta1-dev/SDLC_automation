#pragma once

#include <optional>
#include <string>
#include <vector>

namespace example
{
    struct CartItem
    {
        std::string productId;
        int quantity;
        double unitPrice;
    };

    struct PricingResult
    {
        double subtotal;
        double discount;
        double tax;
        double total;
        std::vector<std::string> warnings;
    };

    class Calculator
    {
    public:
        static int add(int a, int b);
        static std::optional<double> safe_divide(double numerator, double denominator);
        static bool is_even(int value);
        static bool is_seven(int value);
        static bool is_chomu(std::string manager);
        static int minEatingSpeed(std::vector<int> &piles, int h);

        PricingResult calculateFinalCartPrice(
            const std::vector<CartItem> &items,
            const std::string &couponCode,
            bool isPremiumCustomer,
            const std::string &stateCode);
    };

} // namespace example
