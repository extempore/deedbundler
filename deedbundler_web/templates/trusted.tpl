% title = 'Trusted keys'
% rebase('base.tpl', title=title, canonical=False)

<div>
<h2>Trusted keys</h2>
<p>These are the keys currently trusted to post deeds.</p>
<p>Last modified: {{date(modified)}} | Download: <a href="http://deeds.bitcoin-assets.com/trust.json">JSON</a></p>
<table>
  <tr>
    <td>fingerprint</td>
    <td>name</td>
    <td>deeds</td>
    <td>otc</td>
    <td>rating</td>
  </tr>
% for fin in sorted(trusted.keys()):
  <tr>
    <td>{{fin}}</td>
    % name = trusted[fin][0]
    <td>{{name}}</td>
    <td>(<a href="{{user_deeds_url(name)}}">deeds</a>)</td>
    <td>(<a href="{{otc_url(name)}}">otc</a>)</td>
    <td>{{trusted[fin][1]}}</td>
  </tr>
% end
</table>

</div>
