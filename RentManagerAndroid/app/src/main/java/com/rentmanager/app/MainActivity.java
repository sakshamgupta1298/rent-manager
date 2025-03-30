package com.rentmanager.app;

import androidx.appcompat.app.AppCompatActivity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.Toast;

import com.android.volley.Request;
import com.android.volley.RequestQueue;
import com.android.volley.Response;
import com.android.volley.VolleyError;
import com.android.volley.toolbox.JsonObjectRequest;
import com.android.volley.toolbox.Volley;
import com.rentmanager.app.dashboard.TenantDashboardActivity;
import com.rentmanager.app.dashboard.OwnerDashboardActivity;

import org.json.JSONException;
import org.json.JSONObject;

public class MainActivity extends AppCompatActivity {
    private EditText inputTenantId, inputPassword;
    private Button btnLogin;
    private ProgressBar progressBar;
    private RequestQueue requestQueue;
    private SharedPreferences preferences;
    private static final String API_URL = "https://your-rent-manager-api.herokuapp.com/api"; // Replace with your API URL

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // Initialize UI components
        inputTenantId = findViewById(R.id.inputTenantId);
        inputPassword = findViewById(R.id.inputPassword);
        btnLogin = findViewById(R.id.btnLogin);
        progressBar = findViewById(R.id.progressBar);

        // Initialize Volley for network requests
        requestQueue = Volley.newRequestQueue(this);
        
        // Initialize SharedPreferences for storing token
        preferences = getSharedPreferences("RentManagerPrefs", MODE_PRIVATE);
        
        // Check if user is already logged in
        if (isLoggedIn()) {
            navigateToAppropriateScreen();
            return;
        }

        // Login button click listener
        btnLogin.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                attemptLogin();
            }
        });
    }

    private boolean isLoggedIn() {
        return preferences.contains("auth_token") && !preferences.getString("auth_token", "").isEmpty();
    }

    private void navigateToAppropriateScreen() {
        boolean isOwner = preferences.getBoolean("is_owner", false);
        
        if (isOwner) {
            startActivity(new Intent(MainActivity.this, OwnerDashboardActivity.class));
        } else {
            startActivity(new Intent(MainActivity.this, TenantDashboardActivity.class));
        }
        finish();
    }

    private void attemptLogin() {
        String tenantId = inputTenantId.getText().toString().trim();
        String password = inputPassword.getText().toString().trim();
        
        if (tenantId.isEmpty() || password.isEmpty()) {
            Toast.makeText(this, "Please enter both Tenant ID/Email and password", Toast.LENGTH_SHORT).show();
            return;
        }
        
        // Show progress bar
        progressBar.setVisibility(View.VISIBLE);
        btnLogin.setEnabled(false);
        
        try {
            // Create JSON request body
            JSONObject requestBody = new JSONObject();
            requestBody.put("tenant_id", tenantId);
            requestBody.put("password", password);
            
            // Create login request
            JsonObjectRequest loginRequest = new JsonObjectRequest(
                Request.Method.POST,
                API_URL + "/login",
                requestBody,
                new Response.Listener<JSONObject>() {
                    @Override
                    public void onResponse(JSONObject response) {
                        handleLoginResponse(response);
                    }
                },
                new Response.ErrorListener() {
                    @Override
                    public void onErrorResponse(VolleyError error) {
                        progressBar.setVisibility(View.GONE);
                        btnLogin.setEnabled(true);
                        
                        Toast.makeText(MainActivity.this, "Login failed: " + error.getMessage(), Toast.LENGTH_SHORT).show();
                    }
                }
            );
            
            // Add request to queue
            requestQueue.add(loginRequest);
            
        } catch (JSONException e) {
            progressBar.setVisibility(View.GONE);
            btnLogin.setEnabled(true);
            Toast.makeText(this, "Error creating request: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private void handleLoginResponse(JSONObject response) {
        progressBar.setVisibility(View.GONE);
        btnLogin.setEnabled(true);
        
        try {
            String token = response.getString("token");
            JSONObject user = response.getJSONObject("user");
            boolean isOwner = user.getBoolean("is_owner");
            
            // Save to SharedPreferences
            SharedPreferences.Editor editor = preferences.edit();
            editor.putString("auth_token", token);
            editor.putBoolean("is_owner", isOwner);
            editor.putString("user_name", user.getString("name"));
            editor.putInt("user_id", user.getInt("id"));
            
            if (!isOwner && user.has("tenant_id")) {
                editor.putString("tenant_id", user.getString("tenant_id"));
            }
            
            editor.apply();
            
            // Navigate to appropriate screen
            navigateToAppropriateScreen();
            
        } catch (JSONException e) {
            Toast.makeText(this, "Error parsing response: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }
} 