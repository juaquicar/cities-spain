package uk.quijada.ciudades;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** The portal in a full-screen WebView: its own pages stay here, any other link opens in the browser. */
public class MainActivity extends Activity {
    static final String HOST = "spain-cities.quijada.uk";
    static final String HOME = "https://" + HOST + "/";
    static final String OFFLINE = "<html><body style=\"background:#0e1522;color:#ece6d8;font:16px sans-serif;"
        + "display:grid;place-items:center;height:90vh;text-align:center\"><div><h2>Sin conexión</h2>"
        + "<p>Los mapas se descargan de internet.</p><p><a style=\"color:#e7a73c\" href=\"" + HOME
        + "\">Reintentar</a></p></div></body></html>";
    WebView web;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        web = new WebView(this);
        web.setBackgroundColor(0xFF0E1522);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(true);
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
        web.setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        setContentView(web);
        if (state != null) web.restoreState(state);
        else web.loadUrl(start(getIntent()));
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
