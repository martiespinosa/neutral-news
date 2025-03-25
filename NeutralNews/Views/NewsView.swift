//
//  NewsView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/7/25.
//

import SwiftUI

struct NewsView: View {
    let news: News
    let relatedNews: [News]
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack {
                    VStack(alignment: .leading, spacing: 16) {
                        // TODO: Dejar solo la Image cuando haya el logo de todos los medios
                        if let uiImage = UIImage(named: news.sourceMedium.pressMedia.name.normalized()) {
                            Image(uiImage: uiImage)
                                .resizable()
                                .scaledToFit()
                                .frame(height: 30)
                        } else {
                            Text(news.sourceMedium.pressMedia.name)
                                .font(.title)
                                .fontWeight(.semibold)
                                .fontDesign(.serif)
                                .foregroundColor(.secondary)
                        }
                        
                        Text(news.title)
                            .font(.title)
                            .fontWeight(.semibold)
                            .fontDesign(.serif)
                        
                        AsyncImage(url: URL(string: news.imageUrl ?? "")) { image in
                            image.image?
                                .resizable()
                                .scaledToFit()
                        }
                        .frame(maxWidth: .infinity)
                        .clipShape(.rect(cornerRadius: 16))
                        
                        Text(news.description)
                            .fontDesign(.serif)
                        
                        if let link = URL(string: news.link) {
                            Link("Leer en la fuente", destination: link)
                                .fontDesign(.serif)
                        }
                    }
                    .padding()
                    
                    Spacer()
                    
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack {
                            ForEach(relatedNews) { new in
                                NavigationLink(destination: NewsView(news: new, relatedNews: relatedNews)) {
                                    MediaHeadlineView(news: new)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.leading, 16)
                    }
                }
                .frame(minHeight: geometry.size.height)
            }
            .scrollBounceBehavior(.basedOnSize)
            .scrollIndicators(.hidden)
        }
    }
}

#Preview {
    NewsView(news: .mock, relatedNews: [.mock, .mock, .mock])
}
