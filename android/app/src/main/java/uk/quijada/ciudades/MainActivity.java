package uk.quijada.ciudades;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.webkit.GeolocationPermissions;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * The portal in a full-screen WebView: its own pages stay here, any other link opens in the browser. The viewer's
 * "Ver con la cámara" asks for the camera and the location; the app passes those on to Android's own permission dialog.
 */
public class MainActivity extends Activity {
    static final int ASK_CAMERA = 1, ASK_LOCATION = 2;
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
                if (has(Manifest.permission.ACCESS_FINE_LOCATION) || has(Manifest.permission.ACCESS_COARSE_LOCATION)) {
                    cb.invoke(origin, true, false);
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
    }

    boolean has(String permission) {
        return checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
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
