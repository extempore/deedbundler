% title = 'Bundle {0}'.format(address[0:8])
% rebase('base.tpl', title=title, canonical=canonical)

<div class="bundle_meta">
<h3>Bundle <a href="{{canonical}}">{{address}}</a></h3>

<ul>
  <li>deeds: {{num_deeds}}</li>
  <li>created: {{date(created_at)}}</li>
  <li>confirmed: {{date(confirmed_at) if confirmed_at else 'n/a'}}</li>
  <li>address: <a href="https://blockchain.info/address/{{address}}">{{address}}</a></li>
  <li>txid: <a href="https://blockchain.info/tx/{{txid}}">{{txid}}</a></li>
</ul>
</div>

<div class="deeds">
<h3>Deeds included in this bundle</h3>
<table>
  <tr><td>created</td><td>link</td><td>name</td><td>title</td></tr>
% for deed in deeds:
  <tr>
    <td>{{date(deed['created_at'])}}</td>
    <td><a href="{{deed_url(deed['b58_hash'])}}">{{deed['b58_hash']}}</a></td>
    <td>{{deed['otc_name']}}</td>
    <td>{{deed['title'] or ''}}</td>
  </tr>
% end
</table>
</div>

<div class="lite_bundle">
<h3>Lite Bundle</h3>
<p><textarea rows="5" cols="60">{{lite_bundle}}</textarea></p>
</div>

<div class="links">
<a href="{{canonical}}/json">Download JSON</a> | <a href="{{full_bundle}}">Download full bundle</a>
</div>


