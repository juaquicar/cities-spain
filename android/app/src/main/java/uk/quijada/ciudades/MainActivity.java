package uk.quijada.ciudades;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.hardware.Sensor;
import android.hardware.SensorManager;
import android.location.LocationManager;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.webkit.GeolocationPermissions;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

/**
 * The portal in a full-screen WebView: its own pages stay here, any other link opens in the browser. The viewer's
 * "Ver con la cámara" asks for the camera and the location; the app passes those on to Android's own permission dialog.
 * On the first start it asks for both up front, with a word on why, and then checks the location is switched on and the
 * phone has a compass (the compass needs no permission, but not every phone has one).
 */
public class MainActivity extends Activity {
    static final int ASK_CAMERA = 1, ASK_LOCATION = 2, ASK_START = 3;
    static final String[] NEEDED = {Manifest.permission.CAMERA, Manifest.permission.ACCESS_FINE_LOCATION,
        Manifest.permission.ACCESS_COARSE_LOCATION};
    static final String HOST = "spain-cities.quijada.uk";
    static final String HOME = "https://" + HOST + "/";
    static final String OFFLINE = "<html><body style=\"background:#0e1522;color:#ece6d8;font:16px sans-serif;"
        + "display:grid;place-items:center;height:90vh;text-align:center\"><div><h2>Sin conexión</h2>"
        + "<p>Los mapas se descargan de internet.</p><p><a style=\"color:#e7a73c\" href=\"" + HOME
        + "\">Reintentar</a></p></div></body></html>";
    WebView web;
    PermissionRequest cameraAsk;                 // the page's request, waiting for Android's answer
    GeolocationPermissions.Callback whereAsk;
    String whereOrigin;
    SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        web = new WebView(this);
        web.setBackgroundColor(0xFF0E1522);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false); // the camera's picture plays without a second tap
        s.setGeolocationEnabled(true);
        s.setUserAgentString(s.getUserAgentString() + " CiudadesApp/" + BuildConfig.VERSION_NAME);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (HOST.equals(u.getHost())) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                } catch (ActivityNotFoundException e) { /* nothing to open it with */ }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) view.loadDataWithBaseURL(HOME, OFFLINE, "text/html", "utf-8", null);
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest req) {
                boolean ours = HOST.equals(req.getOrigin().getHost());
                boolean video = false;
                for (String r : req.getResources()) video |= PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(r);
                if (!ours || !video) { req.deny(); return; }
                if (has(Manifest.permission.CAMERA)) { req.grant(new String[] {PermissionRequest.RESOURCE_VIDEO_CAPTURE}); return; }
                cameraAsk = req;
                requestPermissions(new String[] {Manifest.permission.CAMERA}, ASK_CAMERA);
            }

            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback cb) {
                if (!HOST.equals(Uri.parse(origin).getHost())) { cb.invoke(origin, false, false); return; }
                if (hasLocation()) {
                    cb.invoke(origin, true, false);
                    checkLocationOn();
                    return;
                }
                whereAsk = cb; whereOrigin = origin;
                requestPermissions(new String[] {Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION}, ASK_LOCATION);
            }
        });
        web.setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        setContentView(web);
        if (state != null) web.restoreState(state);
        else web.loadUrl(start(getIntent()));
        prefs = getSharedPreferences("app", MODE_PRIVATE);
        askAtStart();
    }

    boolean has(String permission) {
        return checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
    }

    boolean hasLocation() {
        return has(Manifest.permission.ACCESS_FINE_LOCATION) || has(Manifest.permission.ACCESS_COARSE_LOCATION);
    }

    // the first time, and again while Android still lets us ask (refused once, not "don't ask again")
    void askAtStart() {
        boolean first = !prefs.getBoolean("asked", false), again = false, missing = false;
        for (String p : NEEDED) if (!has(p)) { missing = true; again |= shouldShowRequestPermissionRationale(p); }
        if (!missing || !(first || again)) { checkLocationOn(); checkCompass(); return; }
        new AlertDialog.Builder(this)
            .setTitle("Ver con la cámara")
            .setMessage("Para poner los edificios sobre la imagen de la cámara, la app necesita:\n\n"
                + "• Cámara: la imagen de la calle.\n"
                + "• Ubicación (GPS): dónde estás, para saber qué edificios tienes alrededor.\n"
                + "• Brújula y giroscopio: hacia dónde miras (no piden permiso).\n\n"
                + "Nada sale del móvil. El mapa funciona igual sin ellos.")
            .setPositiveButton("Continuar", (d, w) -> requestPermissions(NEEDED, ASK_START))
            .setNegativeButton("Ahora no", null)
            .show();
        prefs.edit().putBoolean("asked", true).apply();
    }

    // the location permission is no use with the location switched off
    void checkLocationOn() {
        LocationManager lm = (LocationManager) getSystemService(LOCATION_SERVICE);
        if (!hasLocation() || lm == null || lm.isLocationEnabled()) return;
        new AlertDialog.Builder(this)
            .setTitle("Ubicación desactivada")
            .setMessage("«Ver con la cámara» necesita saber dónde estás. Activa la ubicación del móvil.")
            .setPositiveButton("Activar", (d, w) -> {
                try {
                    startActivity(new Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS));
                } catch (ActivityNotFoundException e) { /* no settings screen */ }
            })
            .setNegativeButton("Ahora no", null)
            .show();
    }

    // once: without a compass the view still works, turned by hand
    void checkCompass() {
        if (prefs.getBoolean("compass", false)) return;
        prefs.edit().putBoolean("compass", true).apply();
        SensorManager sm = (SensorManager) getSystemService(SENSOR_SERVICE);
        boolean compass = sm != null && (sm.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR) != null
            || sm.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD) != null);
        if (!compass) Toast.makeText(this, "Este móvil no tiene brújula: con la cámara, desliza a los lados para orientar la vista.",
            Toast.LENGTH_LONG).show();
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        boolean yes = false;
        for (int r : results) yes |= r == PackageManager.PERMISSION_GRANTED;
        if (code == ASK_CAMERA && cameraAsk != null) {
            if (yes) cameraAsk.grant(new String[] {PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            else cameraAsk.deny();
            cameraAsk = null;
        } else if (code == ASK_LOCATION && whereAsk != null) {
            whereAsk.invoke(whereOrigin, yes, false);
            whereAsk = null;
            checkLocationOn();
        } else if (code == ASK_START) {
            checkLocationOn();
            checkCompass();
        }
    }

    static String start(Intent i) {
        Uri u = i == null ? null : i.getData();
        return u != null && HOST.equals(u.getHost()) ? u.toString() : HOME;
    }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        if (i.getData() != null) web.loadUrl(start(i));
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
