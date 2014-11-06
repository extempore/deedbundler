% title = 'Deed {0}'.format(b58_hash[0:8])
% rebase('base.tpl', title=title, canonical=canonical)

<div class="deed_meta">
<h3>Deed <a href="{{canonical}}">{{b58_hash}}</a></h3>
% if deed_title:
  <h2><em>title:</em> {{deed_title}}</h2>
% end
<ul>
  <li>otc name: <a href="{{otc_url(otc_name)}}">{{otc_name}}</a>
  <li>fingerprint: {{fingerprint}} </li>
  <li>keyid: {{fingerprint[24:]}}</li>
  <li>sha256: {{deed_hash}}</li>
  <li>created: {{date(created_at)}}</li>
  <li>bundled: {{date(bundled_at) if bundled_at else 'pending'}}</li>
% if bundle_address:
  <li>bundle: <a href="{{bundle_url(bundle_address)}}">{{bundle_address}}</a></li>
% end
</div>

<div class="raw_deed">
<h3>Raw deed</h3>
<pre>{{raw_deed}}</pre>

<h3>Base64-encoded deed</h3>
<p><textarea rows="10" cols="80">{{base64_deed}}</textarea></p>
</div>

<div class="links">
<p>
Download deed: 
<a href="{{canonical}}/json">JSON</a> | 
<a href="{{canonical}}/base64">Base64</a> | 
<a href="{{canonical}}/raw">Raw</a>
</p>
</div>

