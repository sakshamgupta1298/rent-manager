package com.rentmanager.app.dashboard;

import androidx.appcompat.app.AppCompatActivity;
import androidx.cardview.widget.CardView;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.android.volley.AuthFailureError;
import com.android.volley.Request;
import com.android.volley.RequestQueue;
import com.android.volley.Response;
import com.android.volley.VolleyError;
import com.android.volley.toolbox.JsonObjectRequest;
import com.android.volley.toolbox.Volley;
import com.rentmanager.app.MainActivity;
import com.rentmanager.app.R;
import com.rentmanager.app.models.Dashboard;
import com.rentmanager.app.payment.PaymentActivity;
import com.rentmanager.app.readings.MeterReadingActivity;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

public class TenantDashboardActivity extends AppCompatActivity {
    private SharedPreferences preferences;
    private RequestQueue requestQueue;
    private SwipeRefreshLayout swipeRefresh;
    private TextView tvWelcome, tvTenantId;
    private TextView tvRentAmount, tvElectricityAmount, tvWaterAmount, tvTotalAmount;
    private CardView cvPaymentStatus;
    private TextView tvPaymentStatus, tvPaymentMethod, tvPaymentAmount, tvPaymentDate, tvPaymentReference;
    private LinearLayout layoutPaymentHistory, layoutElectricityReading, layoutWaterReading;
    private Button btnMakePayment, btnUploadMeterReading;
    private static final String API_URL = "https://your-rent-manager-api.herokuapp.com/api"; // Replace with your API URL
    private static final SimpleDateFormat API_DATE_FORMAT = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US);
    private static final SimpleDateFormat DISPLAY_DATE_FORMAT = new SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.US);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_tenant_dashboard);

        // Initialize preferences and request queue
        preferences = getSharedPreferences("RentManagerPrefs", MODE_PRIVATE);
        requestQueue = Volley.newRequestQueue(this);

        // Initialize UI components
        initializeViews();
        setupListeners();

        // Load dashboard data
        loadDashboardData();
    }

    private void initializeViews() {
        // Welcome section
        tvWelcome = findViewById(R.id.tvWelcome);
        tvTenantId = findViewById(R.id.tvTenantId);

        // Billing section
        tvRentAmount = findViewById(R.id.tvRentAmount);
        tvElectricityAmount = findViewById(R.id.tvElectricityAmount);
        tvWaterAmount = findViewById(R.id.tvWaterAmount);
        tvTotalAmount = findViewById(R.id.tvTotalAmount);

        // Payment status
        cvPaymentStatus = findViewById(R.id.cvPaymentStatus);
        tvPaymentStatus = findViewById(R.id.tvPaymentStatus);
        tvPaymentMethod = findViewById(R.id.tvPaymentMethod);
        tvPaymentAmount = findViewById(R.id.tvPaymentAmount);
        tvPaymentDate = findViewById(R.id.tvPaymentDate);
        tvPaymentReference = findViewById(R.id.tvPaymentReference);

        // Container layouts
        layoutPaymentHistory = findViewById(R.id.layoutPaymentHistory);
        layoutElectricityReading = findViewById(R.id.layoutElectricityReading);
        layoutWaterReading = findViewById(R.id.layoutWaterReading);

        // Action buttons
        btnMakePayment = findViewById(R.id.btnMakePayment);
        btnUploadMeterReading = findViewById(R.id.btnUploadMeterReading);

        // SwipeRefreshLayout
        swipeRefresh = findViewById(R.id.swipeRefresh);
    }

    private void setupListeners() {
        // Set up swipe refresh listener
        swipeRefresh.setOnRefreshListener(new SwipeRefreshLayout.OnRefreshListener() {
            @Override
            public void onRefresh() {
                loadDashboardData();
            }
        });

        // Make Payment button click listener
        btnMakePayment.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startActivity(new Intent(TenantDashboardActivity.this, PaymentActivity.class));
            }
        });

        // Upload Meter Reading button click listener
        btnUploadMeterReading.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startActivity(new Intent(TenantDashboardActivity.this, MeterReadingActivity.class));
            }
        });
    }

    private void loadDashboardData() {
        swipeRefresh.setRefreshing(true);

        JsonObjectRequest dashboardRequest = new JsonObjectRequest(
            Request.Method.GET,
            API_URL + "/tenant/dashboard",
            null,
            new Response.Listener<JSONObject>() {
                @Override
                public void onResponse(JSONObject response) {
                    swipeRefresh.setRefreshing(false);
                    try {
                        updateDashboard(response);
                    } catch (JSONException | ParseException e) {
                        Toast.makeText(TenantDashboardActivity.this, 
                                      "Error parsing dashboard data: " + e.getMessage(), 
                                      Toast.LENGTH_SHORT).show();
                    }
                }
            },
            new Response.ErrorListener() {
                @Override
                public void onErrorResponse(VolleyError error) {
                    swipeRefresh.setRefreshing(false);
                    Toast.makeText(TenantDashboardActivity.this, 
                                  "Failed to load dashboard: " + error.getMessage(), 
                                  Toast.LENGTH_SHORT).show();
                    
                    // If unauthorized, go back to login
                    if (error.networkResponse != null && error.networkResponse.statusCode == 401) {
                        logout();
                    }
                }
            }
        ) {
            @Override
            public Map<String, String> getHeaders() throws AuthFailureError {
                Map<String, String> headers = new HashMap<>();
                headers.put("Authorization", "Bearer " + preferences.getString("auth_token", ""));
                return headers;
            }
        };

        requestQueue.add(dashboardRequest);
    }

    private void updateDashboard(JSONObject response) throws JSONException, ParseException {
        // Update tenant info
        JSONObject tenant = response.getJSONObject("tenant");
        String userName = preferences.getString("user_name", "Tenant");
        tvWelcome.setText("Welcome, " + userName);
        tvTenantId.setText("Tenant ID: " + tenant.getString("tenant_id"));

        // Update billing section
        JSONObject billing = response.getJSONObject("billing");
        tvRentAmount.setText("₹" + formatAmount(billing.getDouble("rent")));
        tvElectricityAmount.setText("₹" + formatAmount(billing.getDouble("electricity")));
        tvWaterAmount.setText("₹" + formatAmount(billing.getDouble("water")));
        tvTotalAmount.setText("₹" + formatAmount(billing.getDouble("total")));

        // Update payment status section
        if (!response.isNull("payment_status")) {
            JSONObject paymentStatus = response.getJSONObject("payment_status");
            cvPaymentStatus.setVisibility(View.VISIBLE);
            btnMakePayment.setVisibility(View.GONE);

            String status = paymentStatus.getString("status");
            tvPaymentStatus.setText(capitalizeFirst(status));
            
            // Set status color
            int statusColor;
            if (status.equals("completed") || status.equals("confirmed")) {
                statusColor = getResources().getColor(R.color.green_500);
            } else if (status.equals("pending")) {
                statusColor = getResources().getColor(R.color.yellow_700);
            } else {
                statusColor = getResources().getColor(R.color.red_500);
            }
            tvPaymentStatus.setTextColor(statusColor);
            
            tvPaymentMethod.setText(capitalizeFirst(paymentStatus.getString("method")));
            tvPaymentAmount.setText("₹" + formatAmount(paymentStatus.getDouble("amount")));
            
            Date paymentDate = API_DATE_FORMAT.parse(paymentStatus.getString("date"));
            tvPaymentDate.setText(DISPLAY_DATE_FORMAT.format(paymentDate));
            
            String reference = paymentStatus.getString("reference");
            tvPaymentReference.setText(reference != null && !reference.equals("null") ? reference : "N/A");
        } else {
            cvPaymentStatus.setVisibility(View.GONE);
            btnMakePayment.setVisibility(View.VISIBLE);
        }

        // Update meter readings
        updateMeterReadings(response.getJSONObject("meter_readings"));

        // Update payment history
        updatePaymentHistory(response.getJSONArray("payment_history"));
    }

    private void updateMeterReadings(JSONObject meterReadings) throws JSONException {
        // Clear previous views
        layoutElectricityReading.removeAllViews();
        layoutWaterReading.removeAllViews();

        // Add electricity reading info
        if (!meterReadings.isNull("electricity")) {
            JSONObject electricity = meterReadings.getJSONObject("electricity");
            View electricityView = getLayoutInflater().inflate(R.layout.item_meter_reading, layoutElectricityReading, false);
            
            TextView tvCurrent = electricityView.findViewById(R.id.tvCurrentReading);
            TextView tvPrevious = electricityView.findViewById(R.id.tvPreviousReading);
            TextView tvConsumption = electricityView.findViewById(R.id.tvConsumption);
            
            tvCurrent.setText("Current: " + electricity.getDouble("current"));
            tvPrevious.setText("Previous: " + electricity.getDouble("previous"));
            tvConsumption.setText("Units: " + electricity.getDouble("consumption"));
            
            layoutElectricityReading.addView(electricityView);
        } else {
            TextView noData = new TextView(this);
            noData.setText("No electricity readings available");
            layoutElectricityReading.addView(noData);
        }

        // Add water reading info
        if (!meterReadings.isNull("water")) {
            JSONObject water = meterReadings.getJSONObject("water");
            View waterView = getLayoutInflater().inflate(R.layout.item_meter_reading, layoutWaterReading, false);
            
            TextView tvCurrent = waterView.findViewById(R.id.tvCurrentReading);
            TextView tvPrevious = waterView.findViewById(R.id.tvPreviousReading);
            
            tvCurrent.setText("Current: " + water.getDouble("current"));
            
            if (!water.isNull("previous")) {
                tvPrevious.setText("Previous: " + water.getDouble("previous"));
            } else {
                tvPrevious.setText("Previous: N/A");
            }
            
            layoutWaterReading.addView(waterView);
        } else {
            TextView noData = new TextView(this);
            noData.setText("No water readings available");
            layoutWaterReading.addView(noData);
        }
    }

    private void updatePaymentHistory(JSONArray paymentHistory) throws JSONException, ParseException {
        // Clear previous payment history
        layoutPaymentHistory.removeAllViews();

        // Add payment history items
        for (int i = 0; i < paymentHistory.length(); i++) {
            JSONObject payment = paymentHistory.getJSONObject(i);
            View paymentView = getLayoutInflater().inflate(R.layout.item_payment_history, layoutPaymentHistory, false);
            
            TextView tvDate = paymentView.findViewById(R.id.tvPaymentDate);
            TextView tvAmount = paymentView.findViewById(R.id.tvPaymentAmount);
            TextView tvMethod = paymentView.findViewById(R.id.tvPaymentMethod);
            TextView tvStatus = paymentView.findViewById(R.id.tvPaymentStatus);
            
            Date paymentDate = API_DATE_FORMAT.parse(payment.getString("date"));
            tvDate.setText(DISPLAY_DATE_FORMAT.format(paymentDate));
            tvAmount.setText("₹" + formatAmount(payment.getDouble("amount")));
            tvMethod.setText(capitalizeFirst(payment.getString("method")));
            
            String status = payment.getString("status");
            tvStatus.setText(capitalizeFirst(status));
            
            // Set status color
            if (status.equals("completed") || status.equals("confirmed")) {
                tvStatus.setTextColor(getResources().getColor(R.color.green_500));
            } else if (status.equals("pending")) {
                tvStatus.setTextColor(getResources().getColor(R.color.yellow_700));
            } else {
                tvStatus.setTextColor(getResources().getColor(R.color.red_500));
            }
            
            layoutPaymentHistory.addView(paymentView);
        }

        if (paymentHistory.length() == 0) {
            TextView noData = new TextView(this);
            noData.setText("No payment history available");
            layoutPaymentHistory.addView(noData);
        }
    }

    private String formatAmount(double amount) {
        return String.format(Locale.US, "%.2f", amount);
    }

    private String capitalizeFirst(String text) {
        if (text == null || text.isEmpty()) {
            return "";
        }
        return text.substring(0, 1).toUpperCase() + text.substring(1);
    }

    private void logout() {
        SharedPreferences.Editor editor = preferences.edit();
        editor.clear();
        editor.apply();
        
        Intent intent = new Intent(TenantDashboardActivity.this, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(intent);
        finish();
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.menu_dashboard, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        int id = item.getItemId();
        
        if (id == R.id.action_logout) {
            logout();
            return true;
        }
        
        return super.onOptionsItemSelected(item);
    }
} 