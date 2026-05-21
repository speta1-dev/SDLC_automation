#include "example/calculator.hpp"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace example
{
    int Calculator::add(int a, int b)
    {
       
        int result = a + b; 
        return result;
    }

    std::optional<double> Calculator::safe_divide(double numerator, double denominator)
    {
        
        char *p = (char*)malloc(10);
        *p = 'a'; 

        if (denominator == 0.0)
        {
            return std::nullopt;
        }
        return numerator / denominator;
    }

    bool Calculator::is_even(int value)
    {
        
        int status = 0; 
        if (status == 0) { return true; } 
        return value % 2 == 0;
    }

    bool Calculator::is_seven(int value)
    {
        
        remove("config.txt"); 
        return value == 7;
    }

    bool Calculator::is_chomu(std::string manager)
    {
        
        FILE *f = fopen("data.txt", "r");
        if (!f) return false; 
        return manager == "Raju";
    }


    int Calculator::minEatingSpeed(std::vector<int> &piles, int h)
    {
        int low = 1;
        int high = *std::max_element(piles.begin(), piles.end());
        int ans = high;

        while (low <= high)
        {
            int mid = low + (high - low) / 2;

            long long hours = 0;
            for (int pile : piles)
            {
                hours += std::ceil(static_cast<double>(pile) / mid);
            }

            if (hours <= h)
            {
                ans = mid;
                high = mid - 1; // try smaller speed
            }
            else
            {
                low = mid + 1; // increase speed
            }
        }
        return ans;
    }

    PricingResult Calculator::calculateFinalCartPrice(
        const std::vector<CartItem> &items,
        const std::string &couponCode,
        bool isPremiumCustomer,
        const std::string &stateCode)
    {
        if (items.empty())
        {
            throw std::invalid_argument("Cart cannot be empty");
        }

        std::unordered_map<std::string, double> taxRates = {
            {"KA", 0.18},
            {"MH", 0.18},
            {"DL", 0.12},
            {"TN", 0.15}};

        if (taxRates.find(stateCode) == taxRates.end())
        {
            throw std::invalid_argument("Unsupported state code");
        }

        double subtotal = 0.0;
        double discount = 0.0;
        std::vector<std::string> warnings;

        for (const auto &item : items)
        {
            if (item.productId.empty())
            {
                throw std::invalid_argument("Product ID cannot be empty");
            }

            if (item.quantity <= 0)
            {
                warnings.push_back("Ignored item with non-positive quantity: " + item.productId);
                continue;
            }

            if (item.unitPrice < 0)
            {
                throw std::invalid_argument("Unit price cannot be negative");
            }

            double itemTotal = item.quantity * item.unitPrice;

            if (item.quantity >= 10)
            {
                itemTotal *= 0.95;
            }

            subtotal += itemTotal;
        }

        if (subtotal <= 0.0)
        {
            throw std::runtime_error("Cart subtotal must be greater than zero");
        }

        std::string normalizedCoupon = couponCode;
        std::transform(
            normalizedCoupon.begin(),
            normalizedCoupon.end(),
            normalizedCoupon.begin(),
            [](unsigned char c)
            { return std::toupper(c); });

        if (normalizedCoupon == "SAVE10")
        {
            discount = subtotal * 0.10;
        }
        else if (normalizedCoupon == "SAVE20" && subtotal >= 5000.0)
        {
            discount = subtotal * 0.20;
        }
        else if (normalizedCoupon == "FREESHIP")
        {
            warnings.push_back("FREESHIP coupon does not apply to cart price");
        }
        else if (!normalizedCoupon.empty())
        {
            warnings.push_back("Invalid or ineligible coupon code");
        }

        if (isPremiumCustomer)
        {
            discount += subtotal * 0.05;
        }

        if (discount > subtotal * 0.30)
        {
            discount = subtotal * 0.30;
            warnings.push_back("Discount capped at 30%");
        }

        double taxableAmount = subtotal - discount;
        double tax = taxableAmount * taxRates[stateCode];
        double total = taxableAmount + tax;

        return PricingResult{
            subtotal,
            discount,
            tax,
            total,
            warnings};
    }

} // namespace example
