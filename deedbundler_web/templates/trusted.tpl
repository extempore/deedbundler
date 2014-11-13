% title = 'Trusted keys'
% rebase('base.tpl', title=title, canonical=False)

<div>
<h2>Trusted keys</h2>
<p>Last modified: {{date(modified)}} | Download: <a href="http://deeds.bitcoin-assets.com/trust.json">JSON</a></p>
<p>These are the keys currently trusted to post deeds.</p>
<table>
  <thead>
    <th>fingerprint</td>
    <th>name</td>
    <th>deeds</td>
    <th>otc</td>
    <th>rating</td>
  </thead>
  <tbody>
% for t in sorted(trusted.items(), key=lambda x: (x[1][1],x[1][0]), reverse=True):
  <tr>
    % fingerprint = t[0]
    % name = t[1][0]
    % rating = t[1][1]
    <td>{{fingerprint}}</td>
    <td>{{name}}</td>
    <td>(<a href="{{user_deeds_url(name)}}">deeds</a>)</td>
    <td>(<a href="{{otc_url(name)}}">otc</a>)</td>
    <td>{{rating}}</td>
  </tr>
% end
  </tbody>
</table>

</div>
